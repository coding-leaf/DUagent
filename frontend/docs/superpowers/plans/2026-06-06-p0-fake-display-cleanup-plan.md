# P0 前端假展示清理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除或降级 6 个页面中的 Mock/静态假展示指标，消除对验收的误导。

**Architecture:** 纯前端删除/降级。6 个 page 文件 + WORKFLOW.md。不修改 OpenAPI/Backend/Agent/service。每个 task 可单独 lint/build 验证、单独提交。

**Tech Stack:** React, Tailwind CSS, JavaScript

**依据 Spec：** `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md` §8-9

---

### Task 1: StudentProfile — 删除学习动力指数和认知成长曲线，降级雷达图

**Files:**
- Modify: `src/pages/StudentProfile.jsx`

**操作：**

1. 删除 `learning_motivation`、`motivation_percentile` 从 profileData 解构（第 44 行）
2. 删除 `cognitive_growth` 从 effectsData 解构（第 45 行）
3. 删除"学习动力指数"卡片区域（第 82-89 行）
4. 删除"认知成长曲线"section（第 242-261 行，含标题和两处 `cognitive_growth?.map`）
5. 降级 RadarChart 数据源：当前第 104-109 行使用硬编码静态数组。将 RadarChart 区域标注为占位——隐藏图表并显示"模态偏好数据待 Backend 返回"文案
6. `total_duration_hours` 展示处（第 229 行）保留但改为 `{total_duration_hours ? total_duration_hours + 'h' : '待统计'}`

**验证：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```

**提交：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/StudentProfile.jsx
git commit -m "StudentProfile 删除学习动力指数和认知成长曲线,降级雷达图"
```

---

### Task 2: ResourceDetail — 删除建议学习时长

**Files:**
- Modify: `src/pages/ResourceDetail.jsx`

**操作：**

删除第 75-76 行的"建议用时"展示块：
```jsx
<span className="text-[10px] text-outline">建议用时</span>
<span className="font-bold text-on-surface">25m</span>
```

**验证：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```

**提交：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/ResourceDetail.jsx
git commit -m "ResourceDetail 删除建议学习时长静态展示"
```

---

### Task 3: PracticeResult — 删除历史击败/新纪录/排名

**Files:**
- Modify: `src/pages/PracticeResult.jsx`

**操作：**

1. 删除第 106 行的"新纪录"badge
2. 删除第 124 行的"历史击败"展示及相关容器

**验证：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```

**提交：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/PracticeResult.jsx
git commit -m "PracticeResult 删除新纪录和历史击败静态展示"
```

---

### Task 4: LearningPath — 降级静态提示和推荐卡

**Files:**
- Modify: `src/pages/LearningPath.jsx`

**操作：**

1. 删除或降级第 106-112 行的"欠缺知识点推荐"和"配套习题"（改为通用占位文案或隐藏）
2. 删除或降级第 136 行的"关键缺失: 旋转平衡因子"（改为通用说明或删除）
3. 删除或降级第 144 行的"智能体提示"（改为通用占位）
4. 检查并降级静态推荐资源卡

**验证：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```

**提交：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/LearningPath.jsx
git commit -m "LearningPath 降级静态个性化提示和推荐卡"
```

---

### Task 5: TeacherConsole — 删除 mock 专属覆盖率/重点关注学生

**Files:**
- Modify: `src/pages/TeacherConsole.jsx`

**操作：**

删除 `useMock &&` Insights 区块内的 mock 专属展示（均在 `{useMock && (` 守卫内，本次只删除 mock 内容，不删除 useMock && 守卫本身——该守卫是阶段二第二轮 P0 待整体移除项）：
1. 第 274 行"平均活跃时间"
2. 第 278 行"知识点覆盖率"
3. 第 288 行"需重点关注学生 (Special Students)"及其 `special_students` 列表

**验证：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```

**提交：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/TeacherConsole.jsx
git commit -m "TeacherConsole 删除 mock 专属覆盖率、重点关注学生等假展示"
```

---

### Task 6: TeacherStudentReport — 删除 mock 分支非契约字段，修正注释

**Files:**
- Modify: `src/pages/TeacherStudentReport.jsx`

**操作：**

删除 mock 分支（`useMock` 为 true 时渲染的丰富视图）中的非契约字段：
1. 第 126 行 `report.class_name` — 删除
2. 第 135 行 `report.total_duration_hours` — 删除
3. 第 139 行 `report.rank` — 删除
4. 第 150-151 行 `report.motivation_index` 学习动力指数 — 删除
5. 第 293 行 `report.total_duration_hours`（另一处）— 删除
6. 第 306 行 认知成长曲线 — 删除

修正注释误判：
1. 第 537 行 `{/* weak_points — 不在正式 StudentLearning 契约中 */}` → 改为 `{/* weak_points — 后端当前返回空数组，等待 Backend 聚合实现 */}`
2. 第 561 行 `{/* recent_activity — 不在正式 StudentLearning 契约中 */}` → 改为 `{/* recent_activity — 后端当前返回空数组，等待 Backend 聚合实现 */}`

**验证：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

**提交：**
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/TeacherStudentReport.jsx
git commit -m "TeacherStudentReport 删除 mock 分支非契约字段,修正 weak_points 注释"
```

---

### Task 7: 全量验证 + WORKFLOW 收口

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 2: 更新 WORKFLOW.md**

在 `## 最近验证` 末尾追加：

```markdown
- 2026-06-06：P0 前端假展示清理完成：
  - StudentProfile：删除学习动力指数、认知成长曲线；RadarChart 降级为占位；total_duration_hours 改为"待统计"
  - ResourceDetail：删除"建议用时 25m"静态展示
  - PracticeResult：删除"新纪录""历史击败"展示
  - LearningPath：降级静态个性化提示和推荐卡
  - TeacherConsole：删除 mock Insights 内覆盖率、重点关注学生等假展示
  - TeacherStudentReport：删除 mock 分支 class_name/rank/motivation_index/total_duration_hours/认知曲线；修正 weak_points/recent_activity 注释（从"不在契约"改为"后端空数组"）
  - `npm run lint` / `npm run build` 通过。无 OpenAPI/契约漂移。
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "记录 P0 前端假展示清理完成"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ Task 1-6 覆盖审查文档 §8-9 列出的全部删除/降级项。

**2. 无占位符：** ✅ 每 task 有具体行号和操作描述。

**3. 类型一致性：** ✅ 纯删除/降级，无新接口或新类型。

## 验证

| 方式 | 内容 |
|------|------|
| `npm run lint` | 每个 Task |
| `npm run build` | Task 6-7 |
| 手工 | 学生/教师登录确认假指标已消失 |
