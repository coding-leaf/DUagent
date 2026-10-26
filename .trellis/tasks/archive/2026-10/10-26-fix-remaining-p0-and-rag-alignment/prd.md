# 收口剩余 P0 安全越权、RAG 错位与前端交互缺陷

## Goal

全面审核前四阶段任务（安全基线、AgentScope 2.0.10 编排、通用大纲引擎、Ruff 扫描与架构红线）的落地质量，并彻底修复代码审计报告中剩余的跨层 P0 级隐患：后端课程越权（IDOR）、题库生成部分失败误删、跨服务个性化资源 RAG `catalog_id` 错位，以及前端教师退出登录失效与局域网 HTTP 环境 `crypto.randomUUID` 崩溃缺陷。

## Requirements

### 1. 后端接口越权（IDOR）与空会话写入防护 (`backend`)
- **修复 `GET /api/v1/quiz/questions` 越权 (`Backend P0-3`)**：
  - 在 `backend/app/api/v1/quiz.py` 的 `get_questions` 入口处，必须先调用 `await ensure_course_resource_access(db, current_user, course_id)` 校验当前用户对该课程的访问权限（未选课学生返回 403，不存在课程返回 404），防止任意已登录学生遍历 `course_id` 越权读取题库并刷写 `QuizSession`。
- **修复 `GET /api/v1/learning-path` 越权 (`Backend P0-3`)**：
  - 在 `backend/app/api/v1/learning_path.py` 的 `get_learning_path` 中，调用 `await ensure_course_resource_access(db, current_user, course_id)`，统一与 `/nodes/{node_id}/resources` 的权限防线对齐。
  - 更新 `backend/tests/test_learning_path_fallback.py` 中历史遗留的不合理测试数据（例如未创建 `Course` 或未将学生加入 `CourseEnrollment` 的用例，以及对不存在课程断言 404）。

### 2. 题库批量生成部分失败（Partial）防误删保护 (`backend`)
- **修复 `catalog_quiz_generation_service.py` 题库误删 (`Backend P0-5`)**：
  - 在 `generate_quiz_for_child` 成功返回字典中补充 `"node_name": node_name`。
  - 在 `run_quiz_generation_background` 汇总阶段，清理旧 baseline 题库时，**仅清理本次生成成功的知识点节点**（即收集 `completed_node_names = [r["node_name"] for r in results if isinstance(r, dict) and r.get("status") == "completed" and r.get("node_name")]`）：
    - 若 `completed_node_names` 非空，仅对 `QuizQuestion.knowledge_point.in_(completed_node_names)` 且 `~QuizQuestion.id.in_(inserted_question_ids)` 的旧 baseline 题执行软删除（`is_deleted=True`）；
    - 若子任务未携带 `node_name`（兼容无节点名的 mock 场景）且 `failed == 0` 时，才回退到按全目录/全课程清理，**严禁在 `failed > 0`（partial 状态）时无条件按 `~QuizQuestion.id.in_(inserted_question_ids)` 删除失败节点原本正常的存量题库**。

### 3. 跨服务个性化资源生成 RAG 检索 ID 对齐 (`backend` ↔ `agent_service_v2`)
- **修复个性化资源 RAG 检索错位 (`Integration P0-5`)**：
  - Qdrant 向量库在教材入库时以 `catalog_id` 作为 `chunk.metadata.course_id` 索引键，而个性化资源生成（`POST /agent/v2/personalized-resources/generations`）此前仅传了教学班 `course_id`，导致 RAG 检索永远返回 0 条切片。
  - 在 `agent_service_v2/src/agent_service_v2/schemas/personalized_resources.py` 的 `PersonalizedResourceGenerationRequest` 中新增可选字段 `catalog_id: str | None = None`。
  - 在 `agent_service_v2/src/agent_service_v2/generators/personalized_resource_flow.py` 的 `_produce_one` 中：
    - 调用 `writer.write(...)` 时，传入 `course_id=request.catalog_id or request.course_id`（用于 `ResourceWorkerAgent` 向 Qdrant 检索课程教材切片）；
    - 调用 `create_personalized_resource_draft`、`record_personalized_validation`、`review_personalized_resource`、`publish_personalized_resource` 等 Backend 内部工具时，继续传入 `course_id=request.course_id`（保持业务归属为教学班 ID）。
  - 在 `backend/app/api/v1/personalized_resources.py` 与 `backend/app/services/ai_chat_resource_service.py` 构造 `/agent/v2/personalized-resources/generations` 请求负载时，显式传入 `"catalog_id": catalog_context.catalog_id`（或 `catalog.catalog_id`）。

### 4. 前端教师端退出登录与非安全上下文 UUID 崩溃修复 (`frontend`)
- **修复教师控制台“退出登录”按钮无效 (`Frontend P0-3`)**：
  - 在 `frontend/src/pages/TeacherConsole.jsx` 中从 `useAuth()` 解构 `logout`，点击“退出登录”按钮时先执行 `logout()` 清理 `localStorage` 与鉴权上下文，再调用 `navigate('/')`。
- **修复非 HTTPS / 局域网 IP 部署下 `crypto.randomUUID()` 崩溃 (`Frontend P0-4`)**：
  - 新增通用 ID 工具 `frontend/src/utils/id.js`，导出 `uid()` 函数：优先使用 `globalThis.crypto?.randomUUID?.()`，当处于非安全上下文（`crypto.randomUUID` 不存在）时优雅回退至时间戳+随机数拼接方案。
  - 将 `frontend/src/context/ChatContext.jsx`、`frontend/src/utils/chatStreamEvents.js`、`frontend/src/hooks/useRunLogs.js` 中的全部 5 处裸 `crypto.randomUUID()` 替换为 `uid()`。

## Acceptance Criteria

- [x] 未选课学生请求 `GET /api/v1/quiz/questions` 或 `GET /api/v1/learning-path` 返回 403，请求不存在的 `course_id` 返回 404，且不会为越权请求创建 `QuizSession` 记录。
- [x] `run_quiz_generation_background` 在部分子节点失败（`partial`）时，失败节点原有的 baseline 题目保留完好，不被误删。
- [x] 目标驱动与 AI-Chat 触发的个性化资源生成请求均携带 `catalog_id`，Agent 端 `writer.write` 使用 `catalog_id` 检索 Qdrant，而草稿落库与发布仍绑定教学班 `course_id`。
- [x] `TeacherConsole.jsx` 点击“退出登录”后正确调用 `logout()` 并跳转首页。
- [x] `frontend/src/` 下不再直接调用裸 `crypto.randomUUID()`，全部通过 `utils/id.js` 的 `uid()` 安全生成。
- [x] 全仓质量门禁 `python check_all.py`（含前后端 Lint、Vite Build、Backend 单测、Agent Service 单测）以及前端 `npm run test:unit` 100% 通过。
