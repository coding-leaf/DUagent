# 阶段一验收缺陷修复（v2）

**日期**: 2026-06-05
**状态**: 设计中
**范围**: 前端 7 个缺陷 + 未提交候选修复审查 + 可复现 E2E 测试数据

## 背景

阶段一验收发现 7 个缺陷。此前 3 轮提交（8786085、4c27524、ed73f87）完成了页面状态修复和 E2E 用例基础设施，但 HEAD 中缺少 6 个关键修复文件（Login.jsx、CourseContext.jsx、teaching.js、AIChat.jsx、App.jsx、learning.js），导致干净检出无法运行。

这 6 个文件是**候选修复**，需经历契约审查→页面验证→提交流程，不能视为已完成成果。

## 实施批次

### 批次 1: 种子脚本（独立提交）

**文件:**
- Create: `backend/scripts/seed_e2e_data.py`
- Create: `backend/scripts/README.md`（使用说明）

**安全守卫:**
- `ALLOW_E2E_SEED=true` 环境变量，缺失时立即 `sys.exit(1)`
- 数据库名称必须包含 `test`（大小写不敏感），不满足时立即 `sys.exit(1)`
- 不接受命令行参数覆盖守卫

**职责:**
- 复用 Backend `app.core.security` 中的密码哈希函数（`get_password_hash` 或等价函数）
- 使用 Backend ORM 的必填字段与枚举值，不自行编造字段
- 幂等：所有创建操作使用先查后建模式，重复执行不报错、不产生重复记录

**创建的数据:**

| 实体 | 数量 | 说明 |
|------|------|------|
| User | 2 | `s@t.com`（student 角色）、`t@t.com`（teacher 角色），密码 `Abc12345` |
| Course | 2 | 教师关联为 owner，学生通过 join 关联 |
| CourseKnowledgeGraph | 2 门 × N nodes + edges | 供 learning-path 查询 |
| Resource | 每门课程若干 | document/mindmap/reading/code/video 类型 |
| QuizQuestion | 每门课程若干 | 供 Quiz 取题 |
| UserProfile | 1（学生） | |
| Evaluation | 每门课程 1 条（学生） | |
| LearningPath | 每门课程 1 条（学生） | |
| QuizSession | 1+ 已完成会话 | 供教师端 Quiz 统计 |

**环境要求:**
- 后端使用专用测试数据库启动（如 `DB_NAME=duagent_test`），**不允许对开发数据库执行种子脚本**
- 种子脚本读取与该后端相同的数据库配置（通过 Backend 的 `Settings` 或环境变量）
- Playwright 只连接该测试后端

**运行命令:**
```bash
ALLOW_E2E_SEED=true python scripts/seed_e2e_data.py
npm run test:e2e
```

---

### 批次 2: E2E 基础设施修复（独立提交）

**文件:**
- Modify: `frontend/playwright.config.js`
- Modify: `frontend/e2e/specs.spec.js`

**playwright.config.js:**
- `webServer.env` 添加 `VITE_API_BASE_URL: 'http://localhost:8001/api/v1'`
- 不再依赖本地未跟踪的 `.env`

**specs.spec.js 验证码等待:**
- 等待按钮文本匹配算术题正则（如 `/^\d+\s*[-+*]\s*\d+\s*=\s*\?\s*$/`）后再解析
- 若 5 秒内未匹配到，`expect` 明确失败而非回退 0
- `solveCaptcha()` 解析失败时抛出明确错误，不再静默返回 `"0"`

---

### 批次 3: 5 个候选修复（验证后提交）

**文件:**
- Modify: `Login.jsx`
- Modify: `CourseContext.jsx`
- Modify: `teaching.js`
- Modify: `AIChat.jsx`
- Modify: `App.jsx`

**验证流程（提交前必须全部通过）:**

1. **静态契约核对**

| 文件 | 消费端点 | 需确认字段 |
|------|---------|-----------|
| Login.jsx | POST /auth/login | `data.token`, `data.user`（含 `.role`） |
| CourseContext.jsx | GET /courses | `data.courses[]`（含 `.id`） |
| teaching.js:getClassStudents | GET /teaching/classes/{id}/students | `data.students[]`（含 `major`, `grade`, `joined_at`） |
| teaching.js:getStudentReport | GET /teaching/classes/{id}/students/{id}/learning | 透传 StudentLearning |
| AIChat.jsx | POST /tutoring/chat (SSE) | 正式 `knowledge_points`，兼容 `points`/`data` |

2. **curl 验证** — 每个端点用 curl 调真实 API，确认响应形状与前端消费一致

3. **页面验证** — 使用 Playwright MCP：
   - 学生登录 → Dashboard（资源卡片/空状态）
   - 课程切换 → Learning Path 页面
   - Quiz 页面（题目渲染）
   - AI Chat（SSE 连接 + 知识点引用渲染）
   - 教师登录 → TeacherConsole（学生列表、班级切换）
   - TeacherStudentReport（URL 深链 + 正式字段渲染）

4. **weak_points / recent_activity 处理** — 这两个字段不在正式 StudentLearning 契约中。前端在真实模式下必须隐藏对应区块或标记为"未提供"。不能将未声明字段视为正式依赖。

**页面验证的 StudentLearning 正式字段对照:**

| 正式字段 | 页面消费 | 模式 |
|---------|---------|------|
| `student.real_name` / `student.username` | `report.student?.real_name \|\| report.username` | 真实模式 |
| `evaluation_summary.overall_score` | `report.evaluation_summary?.overall_score` | 真实模式 |
| `quiz_stats.total_attempts` / `avg_score` / `avg_time_spent` | `report.quiz_stats?.total_attempts` 等 | 真实模式 |
| `path_progress.current_node` / `completed_nodes` / `total_nodes` | `report.path_progress?.current_node` 等 | 真实模式 |
| `profile_summary.modal_preference` / `knowledge_mastered` / `knowledge_weak` | `report.profile_summary?.modal_preference` 等 | 真实模式 |
| `score`, `rank`, `mastery_stats`, `resource_distribution`, `motivation_index` | 仅在 `useMock` 块内 | Mock 模式 |

---

### 批次 4: TeacherStudentReport 兼容性记录

**文件:** 不修改任何文件（如审查确认无需修改）

**操作:**
- 核对 `TeacherStudentReport.jsx` 真实模式（`!useMock` 分支）所消费的字段
- 确认仅依赖正式 StudentLearning 字段：`student`, `evaluation_summary`, `profile_summary`, `path_progress`, `quiz_stats`
- 确认不消费旧假数据字段（`score`, `rank`, `mastery_stats`, `resource_distribution`, `motivation_index` 等，均在 `useMock` 块内）
- 记录结论："已核对，真实模式仅消费正式 StudentLearning 字段；未发现需要修改的字段映射"

如需修改（发现消费未声明字段、页面渲染异常），则纳入本批次修改 `TeacherStudentReport.jsx`。

---

### 批次 5: learning.js 路径修正（独立提交）

**文件:**
- Modify: `frontend/src/api/services/learning.js`

**修改:** `getTaskStatus(taskId)` 中 `/tasks/${taskId}/status` → `/tasks/${taskId}`

**理由:** GET /api/v1/tasks/{task_id} 在 WORKFLOW.md 中标记为"真实完成"，路径修正独立于 E2E 和页面修复。

---

### 批次 6: WORKFLOW.md 更新

**文件:**
- Modify: `backend/WORKFLOW.md`

**内容:**
- 仅记录已验证通过的提交内容
- E2E 结果按实际写入（3/3 通过才写"通过"；否则写"待账户数据就绪后验收"）
- `npm run lint`、`npm run build`、`npm run test:e2e`、`git diff --check` 全部记录实际值
- 移除所有未经验证的乐观声明

---

## 不提交的文件

- `AGENTS.md` — 外部维护
- `frontend/.gitkeep` — 不在此轮删除
- 工作区 `需求图片/` 目录

## 契约说明

- Client API 契约变化：否
- Agent API 契约变化：否
- 种子脚本不暴露 HTTP 端点，不扩大 API 攻击面
- AI Chat SSE 的 `points`/`data` 是兼容行为，非正式契约字段

## 验证标准

- [ ] 种子脚本可在专用测试 DB 上幂等执行
- [ ] `npm run lint`：0 errors, 0 warnings
- [ ] `npm run build`：通过
- [ ] Playwright MCP 页面验证：学生 + 教师关键链路可用
- [ ] `npm run test:e2e`：3/3 通过
- [ ] `git diff --check`：通过
- [ ] WORKFLOW.md 仅记录实际验证结果
