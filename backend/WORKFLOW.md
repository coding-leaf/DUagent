# WORKFLOW.md

## 接口实现状态维护约定

本文件开头固定维护一份“接口实现情况”总览，用于区分：

- `真实完成`：已接真实鉴权/SQL/Agent 调用，主链路可用
- `半完成`：有真实逻辑，但仍存在硬编码、弱校验、伪异步或部分占位
- `占位/规则完成`：仅完成返回结构、路由或基础协议，业务未真实落地
- `文档声明不做`：当前 v1 契约明确不提供

维护规则：

1. 只要修改了某个接口实现，必须同步更新本文件中的该接口“最近状态”。
2. 更新时至少补充：
   - 修改日期
   - 接口路径
   - 最新状态
   - 一句说明本次变更影响
3. 如果接口从 `占位/规则完成` 提升到 `半完成` 或 `真实完成`，必须直接修改总览表，不允许只写在“最近验证”。
4. 如果接口行为回退、发现假实现、联调不闭环，也必须回写状态，不允许只保留乐观描述。

## 当前接口实现情况总览

更新日期：`2026-06-01`

### 真实完成

- `GET /api/v1/auth/captcha`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `GET /api/v1/courses`
- `POST /api/v1/courses`
- `POST /api/v1/courses/join`
- `GET /api/v1/admin/users`
- `PUT /api/v1/admin/users/{user_id}`
- `DELETE /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/logs/agent`
- `GET /api/v1/admin/logs/operations`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tutoring/conversations`
- `GET /api/v1/tutoring/conversations/{conversation_id}`

### 半完成

- `GET /api/v1/evaluation`
- `POST /api/v1/evaluation/refresh`
- `POST /api/v1/profile/initialize`
- `GET /api/v1/profile`
- `POST /api/v1/profile/refresh`
- `GET /api/v1/learning-path`
- `POST /api/v1/learning-path/refresh`
- `GET /api/v1/quiz/questions`
- `POST /api/v1/quiz/generate`
- `GET /api/v1/quiz/history`
- `GET /api/v1/resources`
- `POST /api/v1/resources/generate`
- `POST /api/v1/tutoring/chat`
- `GET /api/v1/teaching/classes/{class_id}/students`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning`
- `POST /api/v1/webhooks/agent`
- `GET /api/v1/learning-path/nodes/{node_id}/resources`
- `POST /api/v1/quiz/submit`
- `GET /api/v1/quiz/result`

### 占位/规则完成

_（当前无占位接口）_

### 文档声明不做

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/send-reset-code`

## 最近状态变更

- `2026-06-01` `接口盘点初始化`
  - 新增接口实现情况总览
  - 明确后续每次改接口时必须同步更新最近状态
- `2026-06-01` `修复 webhook task.status 闭环 + 实现两个占位接口`
  - `POST /api/v1/webhooks/agent`：补充 task.status 设置（completed/failed），幂等保护生效，接口保持「半完成」
  - `GET /api/v1/learning-path/nodes/{node_id}/resources`：新增 `course_id` 查询参数，从 `LearningPath` + `Resource` + `QuizQuestion` 表真实查询，状态提升至「半完成」。同步更新 `docs/10-client-api/Client-API.openapi.json` 补充 `course_id` 参数；已添加课程权限校验（学生需已加入课程）
  - `GET /api/v1/quiz/result`：替换硬编码诊断为基于 `QuizAnswer` JOIN `QuizQuestion` 的数据驱动聚合计算，状态提升至「半完成」。无答题记录时 `diagnosis` 返回 `null`（符合 API 前端接口规范）
- `2026-06-01` `webhook error_code 落库 + 鉴权`
  - `POST /api/v1/webhooks/agent`：failed 分支补充 `task.error_code` 落库；Agent Service `build_resource_generation_failed_payload` 同步发送 `error_code: "agent_error"`
  - 新增 `X-Webhook-Secret` 鉴权（两端都配同一个 secret 时生效；仅一端配置时，Agent 配 Backend 未配→header 被忽略，Backend 配 Agent 未配→401；两端都不配→跳过鉴权）
- `2026-06-02` `实现 quiz/submit 后台异步 LLM 诊断（修正）`
  - `POST /api/v1/quiz/submit`：评分完成后通过 `asyncio.create_task` 后台异步调用 `agent_client.post_json("/agent/v1/assessment/evaluate")`，LLM 诊断存入 `QuizSession.diagnosis_json`。后台任务使用独立 DB session，不创建 AsyncTask（避免新增未声明 task_type），失败时记录结构化日志。接口保持「半完成」— 诊断链路已打通但依赖后台异步完成
  - `GET /api/v1/quiz/result`：诊断保持纯课程级数据驱动聚合（summary/weak_points/suggestions 全部基于 QuizAnswer JOIN QuizQuestion 计算），不混合 diagnosis_json。接口保持「半完成」— 数据驱动诊断可用，LLM 诊断数据存于 diagnosis_json 供未来 per-session 端点使用
- `2026-06-02` `profile 刷新链路稳定化`
  - `POST /api/v1/profile/refresh`：MySQL `GET_LOCK`/`RELEASE_LOCK` 序列化同用户+课程并发写入；软删旧行 → 插新行；显式 `commit()` 后再释放锁，避免锁释放早于事务提交导致重复活跃行；异常兜底覆盖完整路径（payload 组装 + Agent 调用 + DB 读写 + task 更新），AgentServiceError、锁超时与通用 Exception 分支都会落 `task failed`；GET `/profile` 改为 `.order_by(desc).first()`。接口保持「半完成」— 同步调用 Agent 模式未改为真异步
  - `POST /api/v1/profile/initialize`：同锁策略 + 显式 `commit()` 后释放锁；重复提交 = 覆盖；锁超时返回 `503`

## 文件用途

本文件记录 Backend 联调的开发进度和跨窗口恢复上下文。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前方向

- Backend 已具备对接 Agent Service 的基础：统一的 `AgentClient`、AsyncTask 管理、Webhook 接收落库。
- 6 个 Agent 接口全部完成对接，所有调用统一走 `agent_client` 单例。
- 后续进入联调验证：逐接口启动两个服务，验证完整链路（请求 → Agent 返回 → Backend 落库）。
- 发现的问题优先修 bug，再补 stub。

## Agent Service 接口对接状态

| Backend 接口 | Agent 路径 | 类型 | 状态 | 备注 |
|-------------|-----------|------|------|------|
| `POST /api/v1/profile/refresh` | `/agent/v1/profile/generate` | JSON 同步 | ✅ | 参考实现，payload 从 SQL 聚合 |
| `POST /api/v1/tutoring/chat` | `/agent/v1/tutoring/chat` | SSE 代理 | ✅ | SSE 流透传，累积 chunk 后保存 |
| `POST /api/v1/resources/generate` | `/agent/v1/resources/generate` | 异步+Webhook | ✅ | task_id + webhook_url 传入 |
| `POST /api/v1/quiz/generate` | `/agent/v1/assessment/generate-questions` | 异步 | ✅ | 生成后写 quiz_questions |
| `POST /api/v1/evaluation/refresh` | `/agent/v1/evaluation/generate` | JSON 同步 | ✅ | 聚合学习进度/练习结果 |
| `POST /api/v1/learning-path/refresh` | `/agent/v1/learning-path/generate` | JSON 同步 | ✅ | 传入 evaluation + knowledge_graph |
| `POST /api/v1/webhooks/agent` | — | Webhook | ⚠️ | 见已知问题 |

## 已知问题

1. **Webhook 鉴权需要两端同步配置**（`webhooks.py` + Agent Service `resources.py`）：Backend 已实现 `X-Webhook-Secret` 校验，Agent Service 的 `_post_json_payload` 已同步发送该 header。两端需配置一致的 `WEBHOOK_SECRET` 环境变量，未配时鉴权自动跳过（向后兼容）。
2. **`GET /learning-path/nodes/{id}/resources` chapter_materials 依赖 KG 预置数据**：`chapter_materials` 从 `CourseKnowledgeGraph.nodes` JSON 中提取 `chapter` 字段并匹配 `Resource.chapter`。若 KG 未预置完整数据，该字段将返回空数组（不影响其他字段）。
3. **`POST /quiz/submit` 诊断链路已后台异步化，GET /quiz/result 保持纯课程级**：后台 `_run_diagnosis_background` 通过 `asyncio.create_task` 调用 Agent `/assessment/evaluate`，使用 UPDATE 写入 `QuizSession.diagnosis_json`（无 DB 读依赖，消除竞态）。`GET /quiz/result` 的 summary/weak_points/suggestions 全部基于课程级聚合计算，不混合 `diagnosis_json`（该字段保留供未来 per-session 诊断端点使用）。

## 联调命令

```bash
# Agent Service（agent_service/ 目录，终端 1）
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002

# Backend（backend/ 目录，终端 2）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# 验证 Agent Service 健康
curl http://127.0.0.1:8002/agent/v1/health

# Backend 联调测试
python test_agent_integration.py

# Backend 冒烟测试
python test_api.py

# Agent Service 全量回归
cd agent_service && ./.venv/bin/pytest -q
```

## 测试文件

| 文件 | 用途 | 覆盖范围 |
|------|------|---------|
| `test_agent_integration.py` | Agent 联调集成测试 | 6 个 Agent 接口 + Webhook + 权限 + 降级 |
| `test_api.py` | 全量冒烟测试 | 所有端点的基础可用性 |

## 最近验证

_（联调进行中，逐接口填充）_

## 下一步建议

1. 启动 MySQL 后补跑 `python test_api.py` 和 `python test_agent_integration.py` 确认真实 DB 环境无回归
2. 对 `POST /api/v1/quiz/submit` 的 code / short_answer 题型接入 Agent 深度评估（当前规则比对为大小写不敏感字符串匹配）
3. 视需要补 webhook 鉴权的自动化测试（Backend 配 secret + Agent 未配 → 401 场景）
4. 将 `POST /api/v1/profile/refresh`、`POST /api/v1/evaluation/refresh`、`POST /api/v1/learning-path/refresh` 等接口从「半完成」继续向「真实完成」推进
