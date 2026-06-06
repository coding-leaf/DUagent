# TeacherStudentReport 深度诊断字段扩展设计

> Backend 扩展 StudentLearning API 补 4 个已有数据字段，前端消除 useMock 布局分叉。Agent 零改动。

**最后更新：** 2026-06-06

---

## 1. 目标

消除 `TeacherStudentReport.jsx` 的 `useMock` 布局分叉（mock 分支 20+ fields vs 真实分支 ~10 fields），将 mock 分支中教学场景必须的 4 个能力补入真实契约，删除无契约支撑的假展示。

---

## 2. 范围

**在范围：**

- OpenAPI `StudentLearning` schema 补 4 个字段
- Backend `get_student_learning` 补 4 个数据对象
- Backend 新增 `mastery_breakdown` SQL 聚合（按知识点拆练习正确率）
- 前端 `TeacherStudentReport.jsx` 删除 useMock 分叉，真实分支接入新字段
- 前端顶部教师身份改为真实 useAuth 数据（MS-06 同类问题）

**非目标：**
- 不新增 Agent 端点或 Agent 数据
- 不新增 guidance_suggestion、action_suggestions 等教学建议字段
- 不新增静态图表（SVG 折线图等假展示）

---

## 3. 新增字段：OpenAPI → Backend → Frontend

### 3.1 `evaluation_summary.summary_text`（AI 诊断）

| 层 | 改动 |
|----|------|
| OpenAPI | `evaluation_summary` 新增 `summary_text: string|null` |
| Backend | 读取 `ev.summary_text`（Evaluation 表已有），无数据时 `null` |
| Frontend | 替换 mock 分支的 `ai_insight`（AI 分析）和 `ai_diagnosis`（模态偏好卡底部 AI 诊断） |

**同时修正：** `overall_score` 当前硬编码 `75.0`，改为从 Evaluation 表实际数据计算或留 `null`。

### 3.2 `profile_summary.knowledge_coordinates`（知识坐标数组）

| 层 | 改动 |
|----|------|
| OpenAPI | `profile_summary` 新增 `knowledge_coordinates: array<{name, status, mastered_at}>` |
| Backend | 返回 `pf.knowledge_coordinates`（UserProfile 表 JSON 列，已有），空时 `[]` |
| Frontend | 替换 mock 分支的 `report.knowledge_coordinates`，双色标签列表（mastered 绿/learning 琥珀/其他 灰） |

当前 `profile_summary` 已有 `knowledge_mastered` / `knowledge_weak` counts，保留不变。

### 3.3 `path_progress.nodes`（学习路径节点详情）

| 层 | 改动 |
|----|------|
| OpenAPI | `path_progress` 新增 `nodes: array<{name, status, order}>` |
| Backend | 从 `lp.nodes` JSON 提取 `[{name, status, order}]`，空时 `[]` |
| Frontend | 替换 mock 分支的 `report.learning_path_progress` 表格 |

当前 `path_progress` 已有 `current_node` / `completed_nodes` / `total_nodes`，保留不变。mock 中的 `time`（耗时）和 `completion`（达成率）不补入契约（无对应数据）。

### 3.4 `quiz_stats.mastery_breakdown`（按知识点练习掌握度）

| 层 | 改动 |
|----|------|
| OpenAPI | `quiz_stats` 新增 `mastery_breakdown: array<{knowledge_point, accuracy}>` |
| Backend | SQL 聚合：`QuizAnswer` JOIN `QuizQuestion` GROUP BY `knowledge_point`，`accuracy = SUM(is_correct)/COUNT(*) * 100` |
| Frontend | 替换 mock 分支的 `report.mastery_stats[{name, percent}]` 进度条列表 |

---

## 4. 删除清单（mock 分支专有，不补入契约）

| Mock 字段 | 删除理由 |
|-----------|---------|
| `report.username` | 应用 `student.real_name` |
| `report.major` | 不在契约，非教学核心 |
| `report.ai_diagnosis` | 用 `evaluation_summary.summary_text` 替代 |
| `report.guidance_suggestion` | 学生平台非教师平台 |
| `report.ai_insight` | 用 `evaluation_summary.summary_text` 替代 |
| `report.action_suggestions[]` | 不在契约，Agent 无对应输出 |
| 静态 SVG 折线图卡片 | 假数据，整卡删除 |
| `Prof. Zhang` / `系统管理员` | 改为 `useAuth()` 真实数据 |
| `useMock` 守卫 | 整行删除 |

---

## 5. 前端最终布局（消除分叉后）

```
Header（useAuth 真实数据 + 返回按钮）
├── Profile Banner（student + evaluation_summary.overall_score + summary_text 摘要）
├── Metric Grid（3 列）
│   ├── Quiz Stats（total_attempts / avg_score / avg_time_spent）
│   ├── Path Progress（current_node + completed/total + 进度条）
│   └── Modal Preference（profile_summary.modal_preference 标签）
├── Details
│   ├── Mastery Breakdown（mastery_breakdown 进度条列表）
│   ├── Knowledge Coordinates（knowledge_coordinates 双色标签）
│   ├── Path Nodes（nodes 表格：节点名 + 状态）
│   └── Weak Points + Recent Activity（已有，保留）
```

---

## 6. 文件改动清单

| 文件 | 层 | 改动 |
|------|-----|------|
| `docs/10-client-api/Client-API.openapi.json` | OpenAPI | StudentLearning schema 补 4 字段 |
| `backend/app/api/v1/teaching.py` | Backend | `get_student_learning` 补 4 数据对象 + mastery_breakdown SQL |
| `backend/tests/test_teacher_student_learning.py` | Backend 测试 | 补齐新字段断言 |
| `frontend/src/pages/TeacherStudentReport.jsx` | Frontend | 删除 useMock 分叉 + 接入新字段 + 顶部身份修正 |

---

## 7. 验证

| 方式 | 内容 |
|------|------|
| Backend pytest | 新字段非空断言、空值兜底、mastery_breakdown 计算正确性 |
| `npm run lint` | 零错误 |
| `npm run build` | 通过 |

---

## 自审

1. **无占位符：** ✓
2. **范围：** ✓ OpenAPI + Backend + Frontend 三层对齐，不动 Agent
3. **删除明确：** ✓ 每个 mock 字段有删除理由
4. **数据可达：** ✓ knowledge_coordinates/summary_text/nodes 后端数据已存在，mastery_breakdown 复用现有聚合模式
