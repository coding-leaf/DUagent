# 前后端 API 契约一致性与脱节深度分析报告

本报告根据前端源码实现（Axios 调用及 Mock 逻辑）与后端 API 正式契约（`Client-API.openapi.json`、Pydantic Schema、FastAPI 路由实现）进行深度对比，评估两者之间的脱节程度，并回答“后端 API 是否能承接当前的实现”这一核心问题。

---

## 一、 核心结论：后端 API 能否直接承接当前实现？

**结论：不能直接承接。前后端在接口路径、字段结构、响应格式以及底层数据模型上存在严重的“实质性脱节”。**

若直接关闭前端 Mock 并指向真实后端，系统在 **登录、个人中心、学情展示、AI 答疑、教师端、管理员端** 的几乎所有主流程中都会直接报错崩溃（主要体现为 `404 Not Found`、`422 ValidationError` 以及前端试图读取未定义字段引发的 JS 运行时错误）。

要使系统正常运转，**必须对前端的 API 服务层和组件数据解析层进行重构**，以对齐后端的 OpenAPI 规范（即项目约定的唯一 Source of Truth）。

---

## 二、 关键模块脱节详情与对比

### 1. 认证模块 (Auth)

| 对比项 | 前端实际调用 (Mock/Axios) | 后端契约与实现 (OpenAPI / Pydantic) | 脱节程度与影响 |
| :--- | :--- | :--- | :--- |
| **注册请求** | `POST /auth/register`<br>Payload: `{ registration_code, email, password, username }` | `POST /auth/register`<br>Payload: 额外必填 `captcha_token`, `captcha_code` | **严重脱节**。前端未传递验证码凭证，后端 Pydantic 校验将直接抛出 `422 Unprocessable Entity` 错误，导致注册彻底失效。 |
| **登录响应** | 返回 `{ access_token, refresh_token, user: { role } }` | 返回 `{ token, expires_in, user: { id, email, username, role } }` | **字段名称不符**。前端读取 `access_token` / `refresh_token`，而后端返回的字段是 `token`。后端确实返回了 `user.role`，无需硬编码判断。 |
| **辅助端点** | 实现了 `/auth/logout`, `/auth/refresh`, `/auth/reset-password/code`, `/auth/reset-password` | 后端均未声明或实现以上端点 | **中度脱节**。前端包含登出、刷新 Token 及找回密码功能，后端暂不支持，调用将返回 `404`。 |

---

### 2. 个人画像与学习效果 (Profile & Evaluation)

这是脱节最为严重的灾难区，前端期望的数据格式与后端数据库模型结构完全不一致。

#### 页面 1：个人中心与用户画像 (`StudentProfile.jsx`)
* **接口路径不匹配：** 前端请求 `GET /profile/student`，后端路由为 `GET /profile`（需带 query 参数 `?course_id=...`）。直接请求会导致 `404` 或 `422`。
* **数据字段不匹配：**
  * **前端期望读取的画像基础字段：** `name`, `level`, `title`, `current_course`, `learning_motivation`, `motivation_percentile`, `system_suggestion`, `avatar` 等。
  * **后端返回的画像数据库字段：** `course_id`, `modal_preference`, `guidance_level`, `knowledge_coordinates`, `cognitive_blindspots`, `drive_intent`, `discipline_badge`, `generated_at`。
  * **模态偏好字段冲突：** 前端期望为 `modality_preference: { visual, auditory, reading, kinesthetic }`；后端返回为 `modal_preference: { video_animation, chart_logic, text_analysis, code_practice, formula_derivation }`。
  * **引导粒度字段冲突：** 前端期望 `granularity_level: "L2"`（直接字符串）；后端返回 `guidance_level: { current: "L2", updated_at: "..." }`（嵌套对象）。

#### 页面 2：学习效果评估 (`LearningEffects.jsx`)
* **接口路径不匹配：** 前端请求 `GET /evaluation/learning-effects`，后端路由为 `GET /evaluation`（需带 query `?course_id=...`）。
* **数据结构完全脱节：**
  * **前端期望：** 返回 `weekly_max_accuracy`, `total_duration_hours`, `knowledge_nodes` (掌握度数组), `cognitive_growth` (月度成长折线图数组)。
  * **后端返回：** 专为大模型表格展示设计的结构：
    ```json
    {
      "course_id": "...",
      "progress_table": { "columns": [], "rows": [] },
      "mastery_table": { "columns": [], "rows": [] },
      "resource_usage_table": { "columns": [], "rows": [] },
      "summary_text": "AI生成的文字总结"
    }
    ```
  * **影响：** 前端目前将效果展示表和 Donut 饼图数据完全硬编码在 JSX 中，但进度条依然试图遍历 `effectsData.knowledge_nodes`，这在后端返回中是不存在的，会导致页面无法展示掌握度进度条。

---

### 3. AI 答疑智能辅导 (AIChat / Tutoring)

前端实现的答疑聊天室与后端基于多智能体 SSE 设计的流式答疑接口存在根本性脱节。

| 维度 | 前端实际调用 (Mock/Axios) | 后端契约与实现 (OpenAPI / SSE) | 脱节程度与影响 |
| :--- | :--- | :--- | :--- |
| **会话列表** | `GET /api/v1/chat/sessions` | `GET /tutoring/conversations` | **接口不符**。双重路径前缀（`/api/v1/api/v1/...`）及端点名差异，返回 `404`。 |
| **历史记录** | `GET /api/v1/chat/history?session_id=...` | `GET /tutoring/conversations/{id}` | **接口不符**。参数传递方式与路径不同，返回 `404`。 |
| **发送消息** | `POST /api/v1/chat/completions`<br>Payload: `{ session_id, message }`<br>返回格式：普通 Axios JSON 阻塞返回 | `POST /tutoring/chat`<br>Payload: `{ conversation_id, message, course_id, scope }`<br>返回格式：**SSE (text/event-stream) 流式响应** | **致命脱节**。前端使用普通的 Axios Promise 方式拦截消息发送，不支持流式解析（SSE）。一旦切换真实后端，前端将无法正确渲染打字机效果的流式文本。 |

---

### 4. 异步任务轮询与 Webhook (Tasks & Webhook)

* **轮询接口后缀不一致：**
  * 前端请求：`GET /tasks/{task_id}/status`
  * 后端提供：`GET /tasks/{task_id}` （该接口直接返回包含 status 的任务实体）
  * **影响：** 前端轮询状态时会收到 `404` 错误，导致所有需要异步生成/刷新的任务（如：路径生成、测试生成、资料生成）都卡在“生成中/排队中”状态无法结束。

---

### 5. 教师端控制台与报告 (Teaching)

教师端对于班级选择、学情监控的接口定义发生了重构。

| 功能描述 | 前端实际调用 (Mock/Axios) | 后端契约与实现 (OpenAPI) | 脱节程度与影响 |
| :--- | :--- | :--- | :--- |
| **班级/课程列表** | `GET /api/v1/teacher/classes` | `GET /courses` (教师与学生共用此列表) | 前端请求报 `404`。 |
| **学生名册列表** | `GET /api/v1/course/{courseId}/students` | `GET /teaching/classes/{class_id}/students` | 前端请求报 `404`。 |
| **AI 洞察数据** | `GET /api/v1/course/{courseId}/insights` | **后端不存在此接口**。正式契约中没有班级 AI 洞察接口，也没有被其他接口承接。 | **严重脱节**。前端看板的 AI 洞察模块（平均活跃时间、覆盖率）由于没有真实接口，在阶段一联调中必须进行**隐藏或屏蔽**。 |
| **学生学情报告** | `GET /api/v1/teacher/students/{studentId}/report` | `GET /teaching/classes/{class_id}/students/{student_id}` (个人信息)<br>`GET /teaching/classes/{class_id}/students/{student_id}/learning` (学情评估) | 前端试图用一个 API 拿完所有画像与评估，而后端将其拆分为了基础画像与学情评估两个端点。 |

---

### 6. 管理员端 (Admin)

管理员端存在单复数 and 命名上的小幅脱节。
* **智能体日志：** 前端请求 `/admin/logs/agents`，后端为 `/admin/logs/agent`（单数）。
* **系统基础日志：** 前端请求 `/admin/logs/system` , 后端为 `/admin/logs/operations`。
* **影响：** 管理员后台日志审计功能在真实环境下返回 `404`。

---

## 三、 对后端的承接能力评估

### 后端 API 能承接什么？
根据当前项目 `WORKFLOW.md` 的进度记录，后端目前处于 **半完成状态**：
1. **数据模型与存储：** 后端承接了 `backend/schema.sql` 物理表的增删改查逻辑。
2. **多智能体交互与任务机制：** 拥有基本的异步任务处理与 Webhook 接收框架。

### 后端承接能力的局限性 (不可过度表述)
在当前联调阶段，后端 API 仍有大量**硬编码或未完全实现的业务指标**，前端无法通过 API 获得动态真实值：
1. **学生列表没有整体掌握度数据：** 教师端调用的学生列表接口 `GET /teaching/classes/{class_id}/students` **根本不返回任何课程整体掌握度指标**。
2. **学生学情汇总数据硬编码：** 获取单个学生学情评估的接口 `GET /teaching/classes/{class_id}/students/{student_id}/learning` 中，返回的 `evaluation_summary.overall_score` 指标在后端目前被**强行硬编码返回固定值 75.0**。
3. **评估时长占位：** 评估数据中的累计学习时长在后端目前为 **零值占位** 状态，不反映学生的真实阅读时间。
4. 因此，后端无法支持前端全部拟真的学情画像，阶段一中前端页面需要隐藏或重构这些不完整的指标，仅做基础字段对接。
