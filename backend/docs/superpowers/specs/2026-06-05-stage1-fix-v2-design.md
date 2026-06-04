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
| UserProfile | 每门课程 1 条（学生） | 供课程切换时两门课程均有画像数据 |
| Evaluation | 每门课程 1 条（学生） | |
| LearningPath | 每门课程 1 条（学生） | |
| QuizSession | 1+ 已完成会话 | 供教师端 Quiz 统计 |

**环境要求:**
- 后端使用专用测试数据库启动（如 `DB_NAME=duagent_test`），**不允许对开发数据库执行种子脚本**
- 种子脚本读取与该后端相同的数据库配置（通过 Backend 的 `Settings` 或环境变量），确保两者连接同一数据库
- Playwright 只连接该测试后端

**完整启动与运行顺序:**
```bash
# 0. 创建测试数据库（如不存在）
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS duagent_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 1. 启动 Agent Service
cd agent_service && ./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002 &

# 2. 使用测试 DB 启动 Backend（显式 DATABASE_URL 覆盖 .env）
cd backend && DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 &

# 3. 执行种子脚本（使用相同 DATABASE_URL）
cd backend && ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py

# 4. 运行 E2E（Playwright webServer 自动启动前端并注入 VITE_API_BASE_URL）
cd frontend && npm run test:e2e
```

Backend 与种子脚本使用同一 DATABASE_URL；Playwright 前端通过 VITE_API_BASE_URL 连接该 Backend。

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

**页面验证的 StudentLearning 正式字段对照:**

| 正式字段 | 页面消费 | 模式 |
|---------|---------|------|
| `student.real_name` / `student.student_id` | `report.student?.real_name \|\| report.student?.student_id` | 真实模式 |
| `evaluation_summary.overall_score` | `report.evaluation_summary?.overall_score` | 真实模式 |
| `quiz_stats.total_attempts` / `avg_score` / `avg_time_spent` | `report.quiz_stats?.total_attempts` 等 | 真实模式 |
| `path_progress.current_node` / `completed_nodes` / `total_nodes` | `report.path_progress?.current_node` 等 | 真实模式 |
| `profile_summary.modal_preference` / `knowledge_mastered` / `knowledge_weak` | `report.profile_summary?.modal_preference` 等 | 真实模式 |
| `score`, `rank`, `mastery_stats`, `resource_distribution`, `motivation_index` | 仅在 `useMock` 块内 | Mock 模式 |

---

### 批次 4: TeacherStudentReport 兼容性修正（独立提交）

**文件:**
- Modify: `TeacherStudentReport.jsx`

**需修改的未声明字段引用（已通过代码审查确认）:**

| 行 | 当前引用 | 问题 | 修正 |
|----|---------|------|------|
| ~92 | `report.username`（标题） | StudentLearning.student 无 username | 改为 `report.student?.real_name \|\| report.student?.student_id \|\| '学生报告'` |
| ~448 | `report.username`（Profile banner） | 同上 | 同上 |
| ~537 | `report.weak_points` | 不在正式契约中 | 隐藏区块或标记"未提供" |
| ~568 | `report.recent_activity` | 不在正式契约中 | 隐藏区块或标记"未提供" |

**正式 StudentLearning 契约仅声明 8 个字段:** student、evaluation_summary、profile_summary、path_progress、quiz_stats、last_message、message_count、updated_at。weak_points 和 recent_activity 不属于正式契约，真实模式不得依赖。

**操作:**
- 将 `report.username` 替换为 `report.student?.real_name || report.student?.student_id || '学生报告'`
- weak_points 区块：当 `report.weak_points` 为空/不存在时显示"未提供"，或直接隐藏该区块
- recent_activity 区块：当 `report.recent_activity` 为空/不存在时显示"暂无数据"，或隐藏该区块
- 不对 useMock 分支做任何修改

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
- E2E 结果按实际写入（3/3 通过才写"通过"；否则写实际失败原因，如后端未启动、Agent 不可用、测试账号缺失、页面渲染错误等）
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
