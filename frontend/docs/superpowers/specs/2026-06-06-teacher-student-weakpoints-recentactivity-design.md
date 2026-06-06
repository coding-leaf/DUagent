# 教师端学生弱项与活动数据聚合设计

> 在 `get_student_learning` 端点补齐 `weak_points`（错题聚合）和 `recent_activity`（最近练习记录），替换 TeacherStudentReport 硬编码空数组。

**日期：** 2026-06-06
**状态：** 设计稿

---

## 1. 目标

将 TeacherStudentReport 页面当前硬编码的 `weak_points: []` 和 `recent_activity: []` 替换为从已有数据表（QuizAnswer + QuizQuestion + QuizSession）聚合的真实数据，消掉教师端个体学生报告的两个空实现。

## 2. 范围与非目标

### 在范围

- Backend `get_student_learning`：`weak_points` 从 `[]` → 按知识点聚合错题 top 5
- Backend `get_student_learning`：`recent_activity` 从 `[]` → 最近 5 次 QuizSession
- OpenAPI `StudentLearning` schema：补 `weak_points[]`、`recent_activity[]` 字段定义
- Frontend `TeacherStudentReport.jsx`：去掉硬编码 `[]`，消费接口真实数据或展示空态
- Backend 测试：403、有错题聚合、无错题空数组、recent_activity 最多 5 条

### 非目标

- 不新增端点
- 不新增数据表或 SQL 迁移
- 不调用 Agent
- 不改 TeacherConsole Insights 区块（`useMock &&` 保留，下一步处理）
- 不改 `teaching.js` 的 `getConsoleInsights` mock

## 3. 契约定义

### 3.1 端点

```
GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning
```

已存在。本轮仅变更 `data.weak_points` 和 `data.recent_activity` 从空数组改为真实聚合。

### 3.2 weak_points

| 字段 | 类型 | 说明 |
|------|------|------|
| `knowledge_point` | string | 知识点名称（过滤空字符串） |
| `error_count` | integer | 错误次数 |
| `total_attempts` | integer | 该知识点答题总数 |
| `error_rate` | number | 错误率 0-1（`error_count / total_attempts`） |

排序：`error_rate DESC, error_count DESC`，取 top 5。

空态：无错题记录时返回 `[]`。

### 3.3 recent_activity

| 字段 | 类型 | 说明 |
|------|------|------|
| `quiz_id` | string | 练习 ID |
| `chapter` | string | 章节 |
| `score` | number | 得分（百分比） |
| `correct_count` | integer | 正确数 |
| `total_count` | integer | 总题数 |
| `time_spent` | integer | 耗时（秒） |
| `created_at` | string | 练习时间，来源于 `QuizSession.create_time`，ISO 格式 |

取最近 5 次 QuizSession，按 `create_time DESC`。

空态：无 QuizSession 时返回 `[]`。

### 3.4 完整响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "student": {"id": "stu_001", "real_name": "张三", "student_id": "20260001"},
    "evaluation_summary": {"overall_score": 75.0, "generated_at": "2026-06-05T10:00:00"},
    "profile_summary": {"knowledge_mastered": 12, "knowledge_weak": 3, "modal_preference": ["visual", "text"]},
    "path_progress": {"current_node": "AVL树旋转", "completed_nodes": 5, "total_nodes": 12},
    "quiz_stats": {"total_attempts": 8, "avg_score": 68.5, "avg_time_spent": 95},
    "weak_points": [
      {"knowledge_point": "AVL树旋转", "error_count": 3, "total_attempts": 5, "error_rate": 0.6},
      {"knowledge_point": "散列冲突", "error_count": 2, "total_attempts": 3, "error_rate": 0.67}
    ],
    "recent_activity": [
      {"quiz_id": "qz_008", "chapter": "树结构", "score": 66.7, "correct_count": 2, "total_count": 3, "time_spent": 120, "created_at": "2026-06-05T10:30:00"}
    ]
  }
}
```

## 4. Backend 实现

`backend/app/api/v1/teaching.py` — `get_student_learning` 函数。

### 4.1 weak_points 聚合

在现有 quiz_stats 和 return 之间插入：

```python
    from sqlalchemy import case

    # weak_points: 按知识点聚合错题 top 5（条件聚合 + 过滤空知识点 + HAVING error_count > 0）
    error_count_expr = func.sum(case((QuizAnswer.is_correct == False, 1), else_=0))
    total_attempts_expr = func.count(QuizAnswer.id)

    weak_points = []
    wp_result = await db.execute(
        select(
            QuizQuestion.knowledge_point,
            total_attempts_expr.label("total_attempts"),
            error_count_expr.label("error_count"),
        )
        .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
        .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
        .where(
            QuizSession.user_id == student_id,
            QuizSession.course_id == class_id,
            QuizSession.is_deleted == False,
            QuizAnswer.is_deleted == False,
            QuizQuestion.is_deleted == False,
            QuizQuestion.knowledge_point != "",
        )
        .group_by(QuizQuestion.knowledge_point)
        .having(error_count_expr > 0)
        .order_by(
            (error_count_expr / total_attempts_expr).desc(),
            error_count_expr.desc(),
        )
        .limit(5)
    )
    for row in wp_result:
        total = row.total_attempts
        errors = row.error_count or 0
        weak_points.append({
            "knowledge_point": row.knowledge_point,
            "error_count": errors,
            "total_attempts": total,
            "error_rate": round(errors / total, 2) if total > 0 else 0,
        })
```

### 4.2 recent_activity 聚合

紧接着：

```python
    # recent_activity: 最近 5 次 QuizSession
    recent_activity = []
    ra_result = await db.execute(
        select(QuizSession)
        .where(
            QuizSession.user_id == student_id,
            QuizSession.course_id == class_id,
            QuizSession.is_deleted == False,
        )
        .order_by(QuizSession.create_time.desc())
        .limit(5)
    )
    for qs in ra_result.scalars().all():
        recent_activity.append({
            "quiz_id": qs.id,
            "chapter": qs.chapter or "",
            "score": qs.score,
            "correct_count": qs.correct_count,
            "total_count": qs.total_count,
            "time_spent": qs.time_spent,
            "created_at": qs.create_time.isoformat() if qs.create_time else "",
        })
```

### 4.3 返回值

`weak_points` 和 `recent_activity` 从 `[]` 改为上述变量。

## 5. 前端改动

`src/pages/TeacherStudentReport.jsx`：

- **weak_points 区块**（当前约第 466 行）：去掉硬编码注释"后端当前返回空数组"。改为从 `reportData.weak_points` 渲染列表，每项显示 `knowledge_point`、`error_count`/`total_attempts`、`error_rate` 百分比。空数组时显示"暂无薄弱点"。
- **recent_activity 区块**（当前约第 490 行）：去掉硬编码注释"后端当前返回空数组"。改为从 `reportData.recent_activity` 渲染列表，每项显示 `created_at`、`chapter`、`score`、`correct_count`/`total_count`。空数组时显示"暂无近期活动"。

不新增 loading/error 状态（reportData 加载态已有父级处理）。

## 6. 验证

- `npm run lint` / `npm run build` 通过
- Backend pytest：403 无权限、有错题聚合返回 non-empty weak_points、无错题返回 []、recent_activity 最多 5 条

## 7. 非目标确认

- 不新增 `GET /teaching/classes/{id}/insights` 端点
- 不调用 Agent
- 不改 `getConsoleInsights` mock
- 不改 TeacherConsole `useMock &&` 守卫
- 不做班级级聚合排名

## 自审

- 无占位符 ✅
- `total_attempts` 使用条件聚合，排序按 `error_rate DESC, error_count DESC` ✅
- 空 `knowledge_point` 过滤 ✅
- `created_at` 来源明确为 `QuizSession.create_time` ✅
