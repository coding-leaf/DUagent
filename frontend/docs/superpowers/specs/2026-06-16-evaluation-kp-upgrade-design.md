# 评估知识点级别精细化 — 设计 spec

**日期：** 2026-06-16  
**目标：** evaluation 升级为知识点粒度，个性化练习成果纳入评估，答题后自动刷新

---

## 改动清单（5 个文件，无新接口，无 DB 变更）

| 层 | 文件 | 改动描述 |
|---|---|---|
| 后端 | `backend/app/api/v1/evaluation.py` | quiz_results 展开为知识点级（JOIN QuizAnswer+QuizQuestion 聚合） |
| Agent schema | `agent_service/schemas/evaluation.py` | QuizResultItem 加 knowledge_point 可选字段 |
| Agent prompt | `agent_service/prompts/evaluation.py` | 输出按知识点的练习趋势 |
| Agent agent | `agent_service/agents/evaluation.py` | mastery_table 改为知识点级聚合 |
| 前端 | `frontend/src/pages/PracticeResult.jsx` | 正确率≥60%时自动触发 refreshEvaluation |

---

## 1. 后端：quiz_results 升级为知识点级

**文件：** `backend/app/api/v1/evaluation.py`

**当前：** 按 QuizSession 聚合，每个 session 一条记录（chapter + score）

**改后：** 按 `(knowledge_point, is_personalized)` 聚合，计算每个知识点的答题次数、平均正确率、最近趋势

**实现逻辑（复用 quiz.py 第 264-281 行的 JOIN 模式）：**

```python
# 在 _assemble_evaluation_payload 里替换 quiz_results 部分

# 1. 取最近 50 个 QuizSession（现有逻辑保持）
quizzes = qz_r.scalars().all()
quiz_ids = [q.id for q in quizzes]

# 2. JOIN QuizAnswer + QuizQuestion，按知识点聚合
kp_stats: dict[str, dict] = {}
if quiz_ids:
    qa_result = await db.execute(
        select(
            QuizAnswer.is_correct,
            QuizAnswer.create_time,
            QuizQuestion.knowledge_point,
            QuizQuestion.chapter,
            QuizQuestion.personalized,
        )
        .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
        .where(
            QuizAnswer.quiz_id.in_(quiz_ids),
            QuizAnswer.is_deleted == False,
            QuizQuestion.is_deleted == False,
        )
        .order_by(QuizAnswer.create_time.asc())
    )
    for row in qa_result.all():
        kp = row.knowledge_point or "未分类"
        if kp not in kp_stats:
            kp_stats[kp] = {
                "chapter": row.chapter or "",
                "total": 0,
                "correct": 0,
                "personalized_count": 0,
                "recent_scores": [],  # 最近 10 次答题正确率（0或1）
            }
        kp_stats[kp]["total"] += 1
        if row.is_correct:
            kp_stats[kp]["correct"] += 1
        if row.personalized:
            kp_stats[kp]["personalized_count"] += 1
        if len(kp_stats[kp]["recent_scores"]) < 10:
            kp_stats[kp]["recent_scores"].append(1 if row.is_correct else 0)

# 3. 构建 quiz_results（知识点级）
payload["quiz_results"] = [
    {
        "knowledge_point": kp,
        "chapter": stats["chapter"],
        "score": round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0.0,
        "total_answers": stats["total"],
        "personalized_count": stats["personalized_count"],
        "recent_trend": round(sum(stats["recent_scores"]) / len(stats["recent_scores"]) * 100, 1)
                        if stats["recent_scores"] else 0.0,
    }
    for kp, stats in kp_stats.items()
]
```

**注意：** Agent schema 的 `QuizResultItem` 需同步更新（见下）。

---

## 2. Agent Schema 更新

**文件：** `agent_service/schemas/evaluation.py`

```python
class QuizResultItem(BaseModel):
    chapter: str = Field(..., description="章节")
    score: float = Field(..., ge=0, le=100, description="正确率")
    created_at: datetime = Field(..., description="完成时间")
    # 新增字段（可选，向下兼容）
    knowledge_point: str | None = Field(None, description="知识点名称")
    total_answers: int | None = Field(None, description="答题总数")
    personalized_count: int | None = Field(None, description="个性化练习次数")
    recent_trend: float | None = Field(None, description="最近10次正确率趋势")
```

**注意：** `created_at` 在新的知识点级数据里没有单次时间戳。改为 Optional：

```python
created_at: datetime | None = Field(None, description="完成时间（session级数据有，知识点聚合数据无）")
```

---

## 3. Agent Prompt 更新

**文件：** `agent_service/prompts/evaluation.py`

**改动点：** `build_evaluation_user_message` 里 quiz_results 部分的输出格式

```python
parts.append("练习结果（按知识点聚合，含个性化练习情况）：")
for item in request.quiz_results:
    kp_label = item.knowledge_point or item.chapter
    trend_text = f"，近期趋势 {item.recent_trend:.1f}%" if item.recent_trend is not None else ""
    personalized_text = f"，其中个性化强化 {item.personalized_count} 次" if item.personalized_count else ""
    parts.append(
        f"  - 「{kp_label}」：正确率 {item.score:.1f}%"
        f"，共答 {item.total_answers or '?'} 题"
        f"{personalized_text}{trend_text}"
    )
```

---

## 4. Agent mastery_table 改为知识点级

**文件：** `agent_service/agents/evaluation.py`

**`_build_mastery_table` 改动：**

```python
def _build_mastery_table(request: EvaluationGenerateRequest) -> TableData:
    # 优先按 knowledge_point 聚合，fallback 到 chapter
    scores_by_kp: dict[str, list[float]] = defaultdict(list)
    kp_to_chapter: dict[str, str] = {}
    personalized_by_kp: dict[str, int] = {}

    for item in request.quiz_results:
        key = item.knowledge_point or item.chapter
        scores_by_kp[key].append(item.score)
        kp_to_chapter[key] = item.chapter
        if item.personalized_count:
            personalized_by_kp[key] = (personalized_by_kp.get(key, 0) + item.personalized_count)

    rows = []
    for kp in sorted(scores_by_kp):
        scores = scores_by_kp[kp]
        average_score = round(sum(scores) / len(scores), 1)
        rows.append({
            "knowledge_point": kp,
            "chapter": kp_to_chapter.get(kp, ""),
            "average_score": average_score,
            "quiz_count": len(scores),
            "personalized_count": personalized_by_kp.get(kp, 0),
            "mastery_level": _mastery_level(average_score),
        })

    return TableData(
        columns=[
            TableColumn(key="knowledge_point", title="知识点"),
            TableColumn(key="chapter", title="章节"),
            TableColumn(key="average_score", title="平均正确率"),
            TableColumn(key="quiz_count", title="练习次数"),
            TableColumn(key="personalized_count", title="强化练习次数"),
            TableColumn(key="mastery_level", title="掌握水平"),
        ],
        rows=rows,
    )
```

**注意：** `_coerce_mastery_table` 里的 whitelist 需同步加 `knowledge_point`、`personalized_count` 字段，否则 LLM enrichment 会被 coerce 掉。

`_observed_chapters` 改为也收集 knowledge_point：

```python
def _observed_chapters(request: EvaluationGenerateRequest) -> set[str]:
    chapters: set[str] = set()
    for item in request.learning_progress.chapter_progress:
        chapters.add(item.chapter)
    for item in request.quiz_results:
        chapters.add(item.chapter)
        if item.knowledge_point:
            chapters.add(item.knowledge_point)
    return chapters
```

---

## 5. 前端：答题后自动触发评估刷新

**文件：** `frontend/src/pages/PracticeResult.jsx`

在组件加载时，若 `accuracy >= 60` 且有 `quizContext`，自动触发一次后台评估刷新：

```jsx
useEffect(() => {
  if (accuracy >= 60 && activeCourseId && resultData) {
    learningService.refreshEvaluation(activeCourseId).catch(() => {});
  }
}, [accuracy, activeCourseId, resultData]);
```

**逻辑：** ≥60% 说明用户有明显进步，值得刷新评估；<60% 说明还需继续练，不浪费评估 token。

---

## 6. 学习效果页前端展示（不改代码，评估已自动升级）

`mastery_table` 现在有 `knowledge_point` 列——学习效果页已有通用表格渲染逻辑，会自动展示新列。无需改 LearningEffects.jsx。

---

## 7. 验证

```bash
# 后端
python3 -m py_compile backend/app/api/v1/evaluation.py
python3 -m py_compile agent_service/schemas/evaluation.py
python3 -m py_compile agent_service/prompts/evaluation.py
python3 -m py_compile agent_service/agents/evaluation.py

# 前端
npm run build
```
