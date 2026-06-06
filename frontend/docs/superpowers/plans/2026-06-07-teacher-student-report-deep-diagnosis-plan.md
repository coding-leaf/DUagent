# TeacherStudentReport 深度诊断字段扩展实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** StudentLearning API 补 3 个真实数据字段 + 前端消除 useMock 分叉。Agent 零改动。

**Architecture:** 三层顺序：OpenAPI 契约补字段 → Backend TDD（红→绿→重构）→ Frontend 删 useMock + 接入新字段 + 修硬编码身份/课程名。每层独立可提交。

**Tech Stack:** FastAPI + SQLAlchemy async (Backend), pytest (Backend 测试), React 19 + Vite 8 + Tailwind CSS 4.3 (Frontend)

---

### Task 1：OpenAPI — StudentLearning schema 补 3 字段

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`（StudentLearning schema）

- [ ] **Step 1：evaluation_summary 新增 summary_text**

在 `evaluation_summary.properties` 内 `generated_at` 之后追加：

```json
"summary_text": {
  "type": "string",
  "nullable": true,
  "description": "AI 评估摘要文本，由 Agent 生成"
}
```

- [ ] **Step 2：profile_summary 新增 knowledge_coordinates**

在 `profile_summary.properties` 内 `modal_preference` 之后追加：

```json
"knowledge_coordinates": {
  "type": "array",
  "description": "知识坐标列表，来自用户画像",
  "items": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "知识点名称"
      },
      "status": {
        "type": "string",
        "description": "掌握状态：mastered / learning"
      },
      "mastered_at": {
        "type": "string",
        "format": "date-time",
        "nullable": true,
        "description": "掌握时间"
      }
    }
  }
}
```

- [ ] **Step 3：quiz_stats 新增 mastery_breakdown**

在 `quiz_stats.properties` 内 `avg_time_spent` 之后追加：

```json
"mastery_breakdown": {
  "type": "array",
  "description": "按知识点拆分的练习正确率",
  "items": {
    "type": "object",
    "properties": {
      "knowledge_point": {
        "type": "string",
        "description": "知识点名称"
      },
      "accuracy": {
        "type": "number",
        "description": "正确率 0-100"
      }
    }
  }
}
```

- [ ] **Step 4：验证 JSON 格式**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && python3 -c "import json; json.load(open('docs/10-client-api/Client-API.openapi.json')); print('JSON valid')"
```

预期：`JSON valid`

- [ ] **Step 5：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add docs/10-client-api/Client-API.openapi.json && git commit -m "docs: StudentLearning 补 summary_text、knowledge_coordinates、mastery_breakdown 字段"
```

---

### Task 2：Backend — TDD 实现 3 个新增字段

**Files:**
- Modify: `../backend/tests/test_teacher_student_learning.py`
- Modify: `../backend/app/api/v1/teaching.py`

- [ ] **Step 1：写失败测试 — summary_text 非空断言**

在 `test_teacher_student_learning.py` 的 `# ===== 2. 200 — weak_points` 区块内，`data = r.json()["data"]` 之后，`chk("200 teacher access", r.status_code == 200)` 之后、`wp = data.get("weak_points", [])` 之前插入：

```python
        ev_sum = data.get("evaluation_summary") or {}
        chk("evaluation_summary has summary_text key", "summary_text" in ev_sum)
```

- [ ] **Step 2：写失败测试 — profile_summary.knowledge_coordinates 断言**

在同一位置继续追加：

```python
        pf_sum = data.get("profile_summary") or {}
        chk("profile_summary has knowledge_coordinates key", "knowledge_coordinates" in pf_sum)
        kc = pf_sum.get("knowledge_coordinates") or []
        chk("knowledge_coordinates is list", isinstance(kc, list))
```

- [ ] **Step 3：写失败测试 — quiz_stats.mastery_breakdown 断言**

继续追加：

```python
        qs = data.get("quiz_stats") or {}
        chk("quiz_stats has mastery_breakdown key", "mastery_breakdown" in qs)
        mb = qs.get("mastery_breakdown") or []
        chk("mastery_breakdown is list", isinstance(mb, list))
        avl_mb = [m for m in mb if m.get("knowledge_point") == "AVL树旋转"]
        chk("AVL树旋转 has mastery_breakdown entry", len(avl_mb) > 0)
        if len(avl_mb) > 0:
            chk("mastery_breakdown has accuracy", "accuracy" in avl_mb[0])
            chk("AVL accuracy = 50.0", avl_mb[0]["accuracy"] == 50.0)
        hash_mb = [m for m in mb if m.get("knowledge_point") == "散列冲突"]
        chk("散列冲突 has mastery_breakdown entry", len(hash_mb) > 0)
        if len(hash_mb) > 0:
            chk("散列冲突 accuracy = 0.0", hash_mb[0]["accuracy"] == 0.0)
```

- [ ] **Step 4：运行测试验证失败**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && uv run python -m pytest tests/test_teacher_student_learning.py -v 2>&1 | tail -20
```

预期：新增断言 FAIL（summary_text key、knowledge_coordinates key、knowledge_coordinates is list、mastery_breakdown key、mastery_breakdown is list、AVL mastery_breakdown entry、AVL accuracy=50.0、散列冲突 entry）

- [ ] **Step 5：Backend — 补 evaluation_summary.summary_text**

在 `teaching.py` 的 `if ev:` 块内 `evaluation_summary` dict 中追加 `summary_text`：

```python
        evaluation_summary = {
            "overall_score": 75.0,
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
            "summary_text": ev.summary_text or None,
        }
```

- [ ] **Step 6：Backend — 补 profile_summary.knowledge_coordinates**

在 `teaching.py` 的 `if pf and pf.knowledge_coordinates:` 块内 `profile_summary` dict 中追加：

```python
        profile_summary = {
            "knowledge_mastered": mastered,
            "knowledge_weak": weak,
            "modal_preference": list(pf.modal_preference.keys()) if pf.modal_preference else [],
            "knowledge_coordinates": pf.knowledge_coordinates if pf.knowledge_coordinates else [],
        }
```

- [ ] **Step 7：Backend — 补 quiz_stats.mastery_breakdown（新 SQL 聚合）**

在 `teaching.py` 的 quiz_stats 计算之后、weak_points 查询之前插入：

```python
        # mastery_breakdown: 按知识点拆正确率（复用 weak_points 聚合模式，无 HAVING 过滤）
        mastery_breakdown = []
        mb_result = await db.execute(
            select(
                QuizQuestion.knowledge_point,
                func.count(QuizAnswer.id).label("total"),
                func.sum(case((QuizAnswer.is_correct == True, 1), else_=0)).label("correct"),
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
        )
        for row in mb_result:
            total = row.total or 0
            correct = row.correct or 0
            mastery_breakdown.append({
                "knowledge_point": row.knowledge_point,
                "accuracy": round(correct / total * 100, 1) if total > 0 else 0,
            })
```

然后将 `mastery_breakdown` 加入 quiz_stats dict 的末尾：

```python
        quiz_stats = {
            "total_attempts": total_attempts,
            "avg_score": round(avg_score, 1),
            "avg_time_spent": int(avg_time),
            "mastery_breakdown": mastery_breakdown,
        }
```

- [ ] **Step 8：运行测试验证通过**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && uv run python -m pytest tests/test_teacher_student_learning.py -v -s 2>&1 | tail -10
```

预期：`0 FAIL`

- [ ] **Step 9：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add backend/app/api/v1/teaching.py backend/tests/test_teacher_student_learning.py && git commit -m "feat: StudentLearning 补 summary_text、knowledge_coordinates、mastery_breakdown 数据对象与测试"
```

---

### Task 3：Frontend — 消除 useMock 分叉 + 接入新字段 + 修硬编码

**Files:**
- Modify: `src/pages/TeacherStudentReport.jsx`

- [ ] **Step 1：替换 imports + 删除 useMock 声明**

当前 imports：
```jsx
import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { teachingService } from '../api/services/teaching';
import FeedbackStatus from '../components/FeedbackStatus';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';
```

替换为：
```jsx
import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { teachingService } from '../api/services/teaching';
import { useCourse } from '../context/CourseContext';
import { useAuth } from '../context/AuthContext';
import FeedbackStatus from '../components/FeedbackStatus';
```

- [ ] **Step 2：获取上下文**

在 `const classId = queryParams.get('course_id');` 之后追加：

```jsx
const { courses } = useCourse();
const { user } = useAuth();
const courseName = courses.find(c => c.id === classId)?.name || '学生报告';
```

- [ ] **Step 3：修正 Header — 真实课程名 + 真实教师身份**

替换 header 内容（`<h1>` 到 `退出登入</button>` 之间的部分）：

```jsx
<h1 className="text-2xl font-bold tracking-tight text-on-surface">{courseName}</h1>
<span className="px-2 py-1 bg-surface-container-high text-primary font-bold text-xs rounded uppercase">教学控制台</span>
```

教师身份区域替换为：
```jsx
<div className="w-10 h-10 rounded-full bg-cyan-500/10 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-sm">
  {(user?.real_name || user?.username || '教').charAt(0)}
</div>
<div className="flex flex-col">
  <span className="text-sm font-bold text-on-surface">{user?.real_name || user?.username || '教师'}</span>
  <span className="text-[10px] text-outline uppercase tracking-wider">
    {{ teacher: '教师', admin: '管理员' }[user?.role] || '教师'}
  </span>
</div>
```

- [ ] **Step 4：删除 useMock 分叉 + 真实分支去壳**

删除 `{useMock && (` 到 `)}` 整段 mock 分支（包含所有 mock 卡片），同时去掉 `{!useMock && (` 和对应 `)}` 包裹，让真实分支 JSX 成为主渲染。具体：

1. 删除第 104-367 行（`{useMock && (` 到对应 `)}`）
2. 删除 `{!useMock && (` 守卫行和对应的 `)}` 闭合标签
3. 保留 `!useMock` 内的所有 JSX 不变

- [ ] **Step 5：Profile banner — 接入 summary_text**

在 Profile banner 内 `evaluation_summary.overall_score` 卡片之后追加：

```jsx
{report.evaluation_summary?.summary_text && (
  <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-100">
    <p className="text-xs text-slate-500 font-bold uppercase mb-1">AI 分析</p>
    <p className="text-sm text-slate-600 leading-relaxed">{report.evaluation_summary.summary_text}</p>
  </div>
)}
```

- [ ] **Step 6：Details — 新增 knowledge_coordinates 卡片**

在 Details grid 中 `weak_points` 卡片之前插入：

```jsx
{/* Knowledge Coordinates */}
<div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
  <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
    <span className="material-symbols-outlined text-cyan-500">grid_view</span>
    知识坐标 (Knowledge Coordinates)
  </h3>
  <div className="flex flex-wrap gap-2">
    {report.profile_summary?.knowledge_coordinates?.length > 0 ? (
      report.profile_summary.knowledge_coordinates.map((kc, i) => {
        const isMastered = kc.status === 'mastered';
        const isLearning = kc.status === 'learning';
        return (
          <span key={i} className={`px-3 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-1.5 ${
            isMastered ? 'bg-green-50 text-green-700 border-green-100' :
            isLearning ? 'bg-amber-50 text-amber-700 border-amber-100' :
            'bg-slate-100 text-slate-400 border-slate-200'
          }`}>
            <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: '"FILL" 1' }}>
              {isMastered ? 'check_circle' : isLearning ? 'sync' : 'help'}
            </span>
            {kc.name}
          </span>
        );
      })
    ) : (
      <p className="text-xs text-outline italic text-center py-4">暂无知识坐标数据</p>
    )}
  </div>
</div>
```

- [ ] **Step 7：Details — 新增 mastery_breakdown 卡片**

继续在 Details grid 中追加：

```jsx
{/* Mastery Breakdown */}
<div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
  <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
    <span className="material-symbols-outlined text-primary text-xl">assessment</span>
    练习掌握度 (Mastery Breakdown)
  </h3>
  {report.quiz_stats?.mastery_breakdown?.length > 0 ? (
    <div className="space-y-3">
      {report.quiz_stats.mastery_breakdown.map((item, i) => (
        <div key={i} className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="font-medium text-on-surface">{item.knowledge_point}</span>
            <span className="font-bold text-primary">{item.accuracy}%</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${item.accuracy}%` }}></div>
          </div>
        </div>
      ))}
    </div>
  ) : (
    <p className="text-xs text-outline italic text-center py-4">暂无练习数据</p>
  )}
</div>
```

- [ ] **Step 8：验证 — lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

预期：lint 零错误，build 通过。

- [ ] **Step 9：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/TeacherStudentReport.jsx && git commit -m "feat: TeacherStudentReport 消除 useMock 分叉，接入新字段，修正身份/课程名硬编码"
```

---

## 任务依赖

```
Task 1（OpenAPI 契约）
  → Task 2（Backend TDD：测试→实现→验证）
    → Task 3（Frontend：删 mock + 接入 + 硬编码修复）
```

严格顺序执行，不可并行。

## 自审

1. **Spec coverage：** 3 字段全覆盖
   - `evaluation_summary.summary_text` → Task 1 Step 1 + Task 2 Step 5 + Task 3 Step 5 ✓
   - `profile_summary.knowledge_coordinates` → Task 1 Step 2 + Task 2 Step 6 + Task 3 Step 6 ✓
   - `quiz_stats.mastery_breakdown` → Task 1 Step 3 + Task 2 Step 7 + Task 3 Step 7 ✓
   - useMock 分叉消除 → Task 3 Step 4 ✓
   - 硬编码修复（教师身份 + 课程名）→ Task 3 Step 2-3 ✓
2. **Placeholder scan：** 无 TBD/TODO ✓
3. **Type consistency：** OpenAPI 字段名与 Backend dict key 对齐，与前端 `report.xxx` 访问路径对齐 ✓
4. **Exclusions honored：** overall_score 不动、path_progress.nodes 不展开 ✓
