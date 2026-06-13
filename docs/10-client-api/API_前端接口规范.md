# Client-API 前端接口规范

> 前端 (Vue3) ↔ Backend (FastAPI, Port 8001)
> 版本: v5.0 | 日期: 2026-05-17

---

## 通用约定

### 返回格式

所有接口统一返回 JSON：

```json
// 成功
{ "code": 200, "message": "success", "data": {} }

// 分页成功
{ "code": 200, "message": "success", "data": { "resources": [], "total": 142, "page": 1, "page_size": 20 } }

// 业务错误
{ "code": 40001, "message": "验证码已过期", "data": null }
```

### 错误码

| HTTP 状态码 | 业务 code 段 | 含义 |
|------------|-------------|------|
| 200 | — | 成功 |
| 201 | — | 创建成功 |
| 400 | 40001-40999 | 参数校验失败 |
| 401 | 40100-40199 | 未认证或 Token 过期 |
| 403 | 40300-40399 | 无权访问 |
| 404 | 40400-40499 | 资源不存在 |
| 409 | 40900-40999 | 冲突（重复注册等） |
| 500 | 50000-50099 | 服务端错误 |

### 认证方式

JWT Bearer Token，登录后获取。Header: `Authorization: Bearer <token>`

- v1 开发阶段只返回单个 JWT `token`
- `token` 有效期可设置为 7 天
- 暂不实现 `refresh_token` 和 `/auth/refresh`
- 带 ~~删除线~~ 的端点无需认证

### 流式响应 (SSE)

请求体仍使用 `Content-Type: application/json`；响应使用 `Content-Type: text/event-stream`。

每条 SSE 消息格式：

```
data: {"type": "chunk", "content": "你好，这道题考察的是..."}
data: {"type": "diagram", "data": "graph TD; A-->B"}
data: {"type": "done", "conversation_id": "conv_xxx"}
```

### 异步任务

刷新/生成类接口返回统一 JSON 包装 + HTTP 202，前端通过 `GET /api/v1/tasks/:task_id` 轮询状态。Backend 负责创建任务、记录任务归属用户和任务类型；Agent Service 只在长任务完成后回调 Backend webhook，前端不直接等待 webhook。

```
POST /xxx/refresh → 202 { "code": 202, "message": "accepted", "data": { "task_id": "..." } }
GET  /tasks/:task_id → 200 { "code": 200, "message": "success", "data": { "task_id": "...", "task_type": "resource_generation", "status": "processing", "progress": 40 } }
```

任务类型统一为：

- `evaluation_refresh`
- `profile_refresh`
- `learning_path_refresh`
- `quiz_generation`
- `resource_generation`

任务状态统一为：`processing` / `completed` / `failed`。v1 不单独引入队列系统，创建后即可记为 `processing`。

**实现方法：**

- Backend 先生成 `task_id`，写入本地任务表，字段至少包含：`task_id`、`task_type`、`user_id`、`course_id`、`status`、`progress`、`result`、`error_message`、`created_at`、`completed_at`。
- 需要调用 Agent 的任务，由 Backend 把同一个 `task_id` 传给 Agent；Agent 回调时原样带回该 `task_id`。
- v1 不要求引入 Redis、Celery 或消息队列。可以用 FastAPI `BackgroundTasks` / 线程 / 简单异步协程执行，数据库任务表作为唯一状态来源。
- `result` 只放摘要 ID 或更新时间，不放大段生成内容；前端完成后再调用对应业务 GET 接口读取最新数据。
- 失败时任务改为 `failed`，写入 `error_message`，前端按失败提示处理即可。

---

## 一、认证 `/api/v1/auth`

### 1.1 获取算术验证码

```
GET /api/v1/auth/captcha
```

**无需认证**

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| captcha_token | string | 验证码标识，注册或登录时回传 |
| captcha_question | string | 数学算式（如 "3 + 5 = ?"） |

**说明：** v1 开发阶段不接入短信/邮件/图形验证码。Backend 生成简单算术题，并在内存中临时保存答案；用户提交后校验 `captcha_token` + `captcha_code`。

### 1.2 注册

```
POST /api/v1/auth/register
```

**无需认证**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| registration_code | string | 是 | 永久注册码，区分角色（如 "teacher"、"student"） |
| email | string | 是 | 邮箱地址 |
| password | string | 是 | 密码（8-32 位，含大小写字母+数字） |
| username | string | 是 | 用户名（3-20 位） |
| real_name | string | 否 | 真实姓名，注册成功后写入用户基础资料 |
| student_id | string | 否 | 学号或工号，注册成功后写入用户基础资料 |
| major | string | 否 | 专业 |
| grade | string | 否 | 年级 |
| guidance_level | string | 否 | 全局引导粒度：L1 / L2 / L3，默认 L2 |
| captcha_token | string | 是 | 算术验证码标识 |
| captcha_code | string | 是 | 算术验证码答案 |

**注册码约定：** v1 开发阶段注册码为永久可复用码：`student` 注册学生账号，`teacher` 注册教师账号；admin 不开放注册，由系统预置。若数据库中存在同名注册码且未删除，使用数据库记录的 `role`；否则 `student` / `teacher` 两个内置码仍可使用。

**审计约定：** 永久注册码不再写 `is_used=true` 或单一 `used_by`。如需记录注册码使用历史，后续应新增注册事件表。

**AI 隐私边界：** `real_name`、`email`、`student_id`、`username` 只能用于账号和业务识别，不得传入 Agent Service。智能辅导后续可使用脱敏学习上下文 `major`、`grade`、`guidance_level`。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| email | string | 邮箱 |
| username | string | 用户名 |

**错误码：**

| code | 说明 |
|------|------|
| 40001 | 注册码无效 |
| 40002 | 验证码错误或过期 |
| 40900 | 邮箱已被注册 |
| 40901 | 用户名已被占用 |

### 1.3 登录

```
POST /api/v1/auth/login
```

**无需认证**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱 |
| password | string | 是 | 密码 |
| captcha_token | string | 是 | 验证码标识 |
| captcha_code | string | 是 | 验证码答案 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| token | string | JWT 访问令牌 |
| expires_in | integer | token 有效期（秒），开发阶段可设置为 7 天 |
| user | object | 用户简要信息 |
| user.id | string | 用户 ID |
| user.email | string | 邮箱 |
| user.username | string | 用户名 |
| user.role | string | 角色：student / teacher / admin |

**错误码：**

| code | 说明 |
|------|------|
| 40002 | 验证码错误或过期 |
| 40100 | 邮箱或密码错误 |

### 1.4 Token 与密码策略

**Token：** v1 开发阶段只使用单个 JWT `token`，通过 `Authorization: Bearer <token>` 鉴权；暂不实现 refresh_token 轮换。

**忘记密码：** v1 不接入邮箱/短信，因此不提供“发送重置密码验证码”和“忘记密码重置”接口。

**管理员重置密码：** 由管理员在 `/api/v1/admin/users/:user_id` 修改用户信息时传入 `new_password` 完成。

---

## 二、用户信息 `/api/v1/users`

### 2.1 获取个人信息

```
GET /api/v1/users/me
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| real_name | string | 真实姓名 |
| student_id | string | 学号或工号 |
| role | string | 角色：student / teacher / admin |
| major | string | 专业 |
| grade | string | 年级 |
| guidance_level | string | 引导粒度：L1 / L2 / L3 |
| created_at | string | 创建时间 ISO 8601 |

**说明：** 个人信息只返回账号基础资料，用于判断当前用户是谁以及角色是什么；学生已加入课程、教师开课列表统一通过 `/api/v1/courses` 获取。用户在某门课内的画像、评估、学习路径、练习记录、资源库等信息不在此接口返回，进入课程后通过对应业务接口按 `course_id` 查询。

### 2.2 修改个人信息

```
PUT /api/v1/users/me
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| real_name | string | 否 | 真实姓名 |
| student_id | string | 否 | 学号或工号 |
| major | string | 否 | 专业 |
| grade | string | 否 | 年级 |
| guidance_level | string | 否 | 引导粒度：L1 / L2 / L3 |

**说明：** email、role 不可通过此接口修改。课程不可通过此接口修改，也不在此接口返回，统一走 `/courses` 域。

**响应 `data`：** 同 `GET /users/me` 的完整个人信息

---

## 三、课程 `/api/v1/courses`

**概念约定：**

- `registration_code` 仅用于账号注册，开发阶段硬编码为 `student` / `teacher`。
- `course_code` 是教师创建课程后生成并分发给学生的课程码，学生通过它加入课程。
- `course_id` 是教师创建的课程/班级空间 ID，v1 中不拆分课程模板与教学班。
- `class_id` 与 `/courses` 返回的 `courses[].id` 同源，仅用于教师视角接口命名。
- 课程知识库由开发者预置并完成向量化，前端不上传课程原始资料；Backend 可为课程默认绑定预置知识库。

### 3.1 我的课程列表

```
GET /api/v1/courses
```

**说明：** 教师返回自己开的班，学生返回自己加入的班。前端课程页/课程按钮使用此接口渲染；用户点击某门课程后，将 `courses[].id` 作为后续接口的 `course_id`。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| courses | array | 课程列表 |
| courses[].id | string | 课程 ID |
| courses[].name | string | 课程名称 |
| courses[].description | string | 课程描述 |
| courses[].course_code | string | 课程码（学生用此码加入） |
| courses[].teacher_name | string | 教师姓名 |
| courses[].student_count | integer | 学生人数 |
| courses[].created_at | string | 创建时间 ISO 8601 |

**课程内个人学习信息：** 进入课程详情后，前端按需调用 `/evaluation?course_id=...`、`/profile?course_id=...`、`/learning-path?course_id=...`、`/resources?course_id=...`、`/quiz/history?course_id=...` 等接口获取当前用户在该课程内的数据。

### 3.2 创建课程 / 开班

```
POST /api/v1/courses
```

**权限：** 仅 teacher

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 课程名称 |
| description | string | 否 | 课程描述 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 课程 ID |
| name | string | 课程名称 |
| course_code | string | 系统自动生成的唯一课程码 |

**错误码：**

| code | 说明 |
|------|------|
| 40300 | 仅教师可创建课程 |

### 3.3 加入课程

```
POST /api/v1/courses/join
```

**权限：** 仅 student

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_code | string | 是 | 课程码 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 课程 ID |
| name | string | 课程名称 |
| teacher_name | string | 教师姓名 |

**错误码：**

| code | 说明 |
|------|------|
| 40301 | 仅学生可加入课程 |
| 40400 | 课程码不存在 |
| 40902 | 已加入该课程 |

---

## 四、教务（教师视角） `/api/v1/teaching`

**页面约定：** 教师进入课程详情页后，先通过 `/teaching/classes/:class_id/students` 获取学生列表；点击某个学生后，通过 `/teaching/classes/:class_id/students/:student_id/learning` 获取该学生在本课程内的只读学习看板。`class_id` 使用 `/courses` 返回的 `courses[].id`。

**权限约定：** 教师只能查看自己创建课程下的学生；Backend 必须校验 `class_id` 属于当前教师，且 `student_id` 已加入该课程。

### 4.1 班级学生列表

```
GET /api/v1/teaching/classes/:class_id/students
```

**权限：** 仅该班级的教师

**说明：** `class_id` 与 `/api/v1/courses` 返回的 `courses[].id` 相同。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| students | array | 学生列表 |
| students[].id | string | 用户 ID |
| students[].username | string | 用户名 |
| students[].real_name | string | 真实姓名 |
| students[].student_id | string | 学号 |
| students[].major | string | 专业 |
| students[].grade | string | 年级 |
| students[].joined_at | string | 加入时间 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

### 4.2 查看学生个人信息

```
GET /api/v1/teaching/classes/:class_id/students/:student_id
```

**权限：** 仅该班级的教师

**说明：** 只读查看学生账号基础资料，不返回课程列表、不返回密码。

**响应 `data`：** 与 `GET /users/me` 结构一致

### 4.3 查看学生学习情况

```
GET /api/v1/teaching/classes/:class_id/students/:student_id/learning
```

**权限：** 仅该班级的教师

**说明：** 教师只读查看学生在该课程内的学习看板，不触发学生画像、评估或学习路径刷新。该接口用于聚合学生端课程详情页的核心展示数据。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| student | object | 学生基础信息 |
| student.id | string | 学生用户 ID |
| student.real_name | string | 真实姓名 |
| student.student_id | string | 学号 |
| evaluation_summary | object | 学习效果评估摘要 |
| evaluation_summary.overall_score | number | 综合评分 0-100 |
| evaluation_summary.generated_at | string | 评估生成时间 |
| profile_summary | object | 用户画像摘要 |
| profile_summary.knowledge_mastered | integer | 已掌握知识点数 |
| profile_summary.knowledge_weak | integer | 薄弱知识点数 |
| profile_summary.modal_preference | array | 模态偏好排行 |
| path_progress | object | 学习路径进度 |
| path_progress.current_node | string | 当前学习节点名称 |
| path_progress.completed_nodes | integer | 已完成节点数 |
| path_progress.total_nodes | integer | 总节点数 |
| quiz_stats | object | 练习统计 |
| quiz_stats.total_attempts | integer | 总练习次数 |
| quiz_stats.avg_score | number | 平均正确率 0-100 |
| quiz_stats.avg_time_spent | integer | 平均耗时（秒） |
| weak_points | array | 薄弱知识点 Top 5，按错误率和错误次数排序 |
| weak_points[].knowledge_point | string | 知识点名称 |
| weak_points[].error_count | integer | 错误次数 |
| weak_points[].total_attempts | integer | 该知识点答题总数 |
| weak_points[].error_rate | number | 错误率 0-1 |
| recent_activity | array | 最近 5 次练习活动，按创建时间倒序 |
| recent_activity[].quiz_id | string | 练习 ID |
| recent_activity[].chapter | string | 章节 |
| recent_activity[].score | number | 得分 0-100 |
| recent_activity[].correct_count | integer | 正确题数 |
| recent_activity[].total_count | integer | 总题数 |
| recent_activity[].time_spent | integer | 耗时（秒） |
| recent_activity[].created_at | string | 完成时间 |

**空态语义：**

- `weak_points: []` 表示当前课程下暂无可聚合的错题知识点，不回退 mock 数据。
- `recent_activity: []` 表示当前课程下暂无练习记录。
- `quiz_stats.avg_score`、`quiz_stats.avg_time_spent` 可为 `0`，表示尚无可统计结果或统计值为 0。

### 4.4 查看班级洞察

```
GET /api/v1/teaching/classes/:class_id/insights
```

**权限：** 仅该班级的教师

**说明：** 提供 TeacherConsole 班级概览所需的最小统计聚合，不返回旧 mock UI 中未进入契约的覆盖率、排名、重点关注学生等字段。

**响应 `data`：`ClassInsights`**

| 字段 | 类型 | 说明 |
|------|------|------|
| avg_quiz_score | number \| null | 班级平均练习分；无练习记录时为 `null` |
| total_quiz_attempts | integer | 班级练习总次数 |
| weak_points_top | array | 班级薄弱知识点 Top 5 |
| weak_points_top[].knowledge_point | string | 知识点名称 |
| weak_points_top[].error_count | integer | 班级错题数 |
| weak_points_top[].total_attempts | integer | 班级该知识点答题总次数 |
| weak_points_top[].error_rate | number | 错误率 0-1 |
| path_node_progress | object | 班级学习路径节点状态分布 |
| path_node_progress.completed | integer | 已完成节点数 |
| path_node_progress.in_progress | integer | 进行中节点数 |
| path_node_progress.recommended | integer | 推荐节点数 |
| path_node_progress.pending | integer | 待学习节点数 |
| path_node_progress.total_nodes | integer | 总节点数 |

**空态语义：**

- `avg_quiz_score: null` 表示班级还没有练习记录，前端显示为空态而不是 0 分。
- `weak_points_top: []` 表示班级暂无可聚合的薄弱知识点。
- `path_node_progress.total_nodes = 0` 且其他节点计数全为 `0` 表示班级暂无学习路径数据。

---

## 五、系统管理 `/api/v1/admin`

### 5.1 用户列表

```
GET /api/v1/admin/users
```

**权限：** 仅 admin

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |
| role | string | 否 | 筛选角色 |
| keyword | string | 否 | 邮箱或用户名模糊搜索 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| users | array | 用户列表 |
| users[].id | string | 用户 ID |
| users[].username | string | 用户名 |
| users[].email | string | 邮箱 |
| users[].real_name | string | 真实姓名 |
| users[].role | string | 角色 |
| users[].major | string | 专业 |
| users[].grade | string | 年级 |
| users[].created_at | string | 创建时间 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

### 5.2 修改用户信息

```
PUT /api/v1/admin/users/:user_id
```

**权限：** 仅 admin

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 否 | 用户名 |
| real_name | string | 否 | 真实姓名 |
| student_id | string | 否 | 学号/工号 |
| role | string | 否 | 角色 |
| major | string | 否 | 专业 |
| grade | string | 否 | 年级 |
| new_password | string | 否 | 管理员重置密码（提供则覆盖旧密码） |

**响应 `data`：** 更新后的用户完整信息

**说明：** 管理员重置密码不需要用户旧密码，也不返回原密码。

### 5.3 移除用户

```
DELETE /api/v1/admin/users/:user_id
```

**权限：** 仅 admin

**响应 `data`：** `{}`

**说明：** 软删除，设置用户状态为 disabled

**错误码：**

| code | 说明 |
|------|------|
| 40401 | 用户不存在 |
| 40302 | 不可移除自己 |

### 5.4 Agent 运行日志

```
GET /api/v1/admin/logs/agent
```

**权限：** 仅 admin

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页条数 |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| logs | array | 日志列表 |
| logs[].timestamp | string | 时间戳 |
| logs[].agent_type | string | Agent 类型：tutoring / evaluation / profile / resource |
| logs[].endpoint | string | 调用的 Agent 接口路径 |
| logs[].latency_ms | integer | 响应延迟（毫秒） |
| logs[].tokens_used | integer | Token 消耗 |
| logs[].status | string | 状态：success / error |
| logs[].error_message | string | 错误信息（成功时为 null） |
| logs[].security_blocked | boolean | 是否触发安全拦截 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

### 5.5 系统运行日志

```
GET /api/v1/admin/logs/operations
```

**权限：** 仅 admin

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码 |
| page_size | integer | 否 | 每页条数 |
| event_type | string | 否 | 事件类型筛选 |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| logs | array | 日志列表 |
| logs[].timestamp | string | 时间戳 |
| logs[].event_type | string | 事件类型：login / logout / operation / system_error / security |
| logs[].user_id | string | 关联用户 ID（系统事件时为 null） |
| logs[].description | string | 事件描述 |
| logs[].ip_address | string | IP 地址 |
| logs[].detail | object | 事件详细数据；系统状态、流量检测、安全合规事件复用该字段承载 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

### 5.6 课程资源库知识图谱生成

#### 5.6.1 管理员查看课程资源库知识图谱状态

```
GET /api/v1/admin/course-catalogs/:catalog_id/knowledge-graphs
```

**权限：** 仅 admin

**说明：** 返回当前资源库通过 `CourseOffering` 绑定的 `course_id`、active KG 摘要和最近一次 `kg_generation` 任务状态。没有 active KG 时 `active_graph=null`。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| catalog_id | string | 课程资源库 ID |
| course_id | string | 通过 CourseOffering 解析出的教学班 / course ID；未绑定时为 null |
| active_graph | object | 当前 active KG 摘要；没有时为 null |
| active_graph.graph_id | string | KG ID |
| active_graph.course_id | string | KG 写入的教学班 / course ID |
| active_graph.version | integer | KG 版本号 |
| active_graph.node_count | integer | 节点数 |
| active_graph.edge_count | integer | 边数 |
| active_graph.source_type | string | 来源类型 |
| active_graph.generation_strategy | string | 生成策略 |
| active_graph.is_active | boolean | 是否 active |
| active_graph.created_at | string | 创建时间 |
| last_generation_task | object | 最近一次 KG 生成任务；没有时为 null |
| last_generation_task.task_id | string | 任务 ID |
| last_generation_task.status | string | processing / completed / failed |
| last_generation_task.progress | integer | 进度 |
| last_generation_task.error_code | string | 错误码 |
| last_generation_task.error_message | string | 错误信息 |
| last_generation_task.created_at | string | 创建时间 |
| last_generation_task.completed_at | string | 完成时间，未完成时为 null |

#### 5.6.2 管理员触发课程资源库知识图谱生成

```
POST /api/v1/admin/course-catalogs/:catalog_id/knowledge-graphs/generations
```

**权限：** 仅 admin

**说明：** 默认基于 CourseCatalog 已入库知识切片自动创建新的 `course_knowledge_graphs` active 版本。请求体可为空，等价于 `{"source_type":"catalog_chunks","activate":true}`。该接口不触发学生个性化 LearningPath 刷新。`kg_json` 保留为后端调试兼容能力，Admin UI 不暴露；`outline_text` 为历史兼容能力。

**请求体 `application/json`：可为空**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_type | string | 否 | catalog_chunks / outline_text / kg_json，默认 catalog_chunks |
| outline_text | string | 条件必填 | `source_type=outline_text` 时必填，课程大纲文本；Admin UI 不暴露 |
| kg_json | object | 条件必填 | `source_type=kg_json` 时必填，包含 nodes 和 edges；后端调试兼容能力，Admin UI 不暴露 |
| activate | boolean | 否 | 生成后是否设为 active 版本，默认 true |

默认自动请求示例：

```json
{}
```

大纲文本兼容请求示例：

```json
{
  "source_type": "outline_text",
  "outline_text": "课程大纲文本",
  "activate": true
}
```

KG JSON 调试请求示例：

```json
{
  "source_type": "kg_json",
  "kg_json": {
    "nodes": [
      { "id": "pointer", "name": "指针", "chapter": "第 6 章 指针" }
    ],
    "edges": []
  },
  "activate": true
}
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |
| catalog_id | string | 课程资源库 ID |
| status | string | 任务状态，创建后为 processing |

**错误码：**

| error_code | 说明 |
|------|------|
| knowledge_base_not_ready | 课程资源库知识库未处于 ready/partial |
| knowledge_base_empty | 课程资源库知识切片为空 |
| offering_missing | 课程资源库尚未绑定 CourseOffering |
| kg_task_running | 已有同一资源库 KG 生成任务进行中 |
| kg_context_empty | 无法从知识库切片构建 KG 上下文 |
| kg_invalid_input | 输入大纲或 KG JSON 无法生成有效图谱 |
| llm_kg_generation_failed | LLM 调用或生成过程失败 |

### 5.7 课程资源库生成资源与软删除

#### 5.7.1 管理员触发课程资源库学习资源生成

```
POST /api/v1/admin/course-catalogs/:catalog_id/resources/generations
```

**权限：** 仅 admin

**说明：** 基于 CourseCatalog 已入库知识生成标准学习资源。Backend 将生成结果按当前绑定该资源库的教学班 fan-out 写入 `resources`；生成后才绑定的教学班不会自动回补。无绑定教学班时返回 `409`。

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chapter | string | 否 | 章节 |
| knowledge_point | string | 否 | 知识点 |
| resource_types | array | 是 | 至少一种资源类型：document / mindmap / reading / code |

`resource_types` 必须至少包含 1 项；缺失或空数组均返回 `42210`。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |
| catalog_id | string | 课程资源库 ID |
| status | string | 任务状态，创建后为 processing |

**错误码：**

| code | 说明 |
|------|------|
| 40913 | 课程资料尚未完成入库 |
| 40914 | 课程知识库为空 |
| 40915 | 课程资源库尚未绑定教学班 |
| 42210 | 资源类型为空或不合法 |

#### 5.7.2 管理员课程资源库生成资源列表

```
GET /api/v1/admin/course-catalogs/:catalog_id/resources
```

**权限：** 仅 admin

**说明：** 聚合当前绑定教学班下未软删除的生成资源，供 Admin 在资源库抽屉中管理。该接口不替代学生端 `GET /resources`。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 资源类型筛选 |
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| resources | array | 生成资源列表 |
| resources[].id | string | 资源 ID |
| resources[].course_id | string | fan-out 后的教学班 ID |
| resources[].title | string | 资源标题 |
| resources[].type | string | 资源类型 |
| resources[].description | string | 资源描述 |
| resources[].tags | array | 标签 |
| resources[].chapter | string | 章节 |
| resources[].knowledge_point | string | 知识点 |
| resources[].view_count | integer | 浏览次数 |
| resources[].created_at | string | 创建时间 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

#### 5.7.3 管理员软删除学习资源

```
DELETE /api/v1/admin/resources/:resource_id
```

**权限：** 仅 admin

**说明：** 仅设置 `Resource.is_deleted=true`，不删除数据库行、文件、Qdrant chunks 或 Agent 产物。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 资源 ID |
| deleted | boolean | 固定为 true |

**错误码：**

| code | 说明 |
|------|------|
| 40412 | 资源不存在 |

#### 5.6.4 管理员软删除课程资源库资料

```
DELETE /api/v1/admin/course-catalogs/:catalog_id/materials/:material_id
```

**权限：** 仅 admin

**说明：** 仅隐藏资料记录，不删除上传文件，不删除 Qdrant chunks，不回滚 `chunk_count`。`ready/partial` 资源库删除资料后 `knowledge_status=dirty`。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 资料 ID |
| catalog_id | string | 课程资源库 ID |
| deleted | boolean | 固定为 true |
| knowledge_status | string | 删除后的知识库状态 |

**错误码：**

| code | 说明 |
|------|------|
| 40411 | 课程资源库资料不存在 |
| 40911 | 课程资源库正在入库中 |

---

## 六、学习效果评估 `/api/v1/evaluation`

### 6.1 获取学习效果评估

```
GET /api/v1/evaluation?course_id={course_id}
```

**说明：** 本接口只读取当前用户在该课程下最近一次学习效果评估，不实时调用 Agent。若尚无足够学习数据或尚未生成评估，返回空表格、空总结和 `generated_at: null`，前端展示空状态或引导完成练习。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| course_id | string | 课程 ID |
| progress_table | object | 学习进度表 |
| progress_table.columns | array | 表头列 |
| progress_table.rows | array | 数据行 |
| mastery_table | object | 知识点掌握程度表 |
| mastery_table.columns | array | 表头列 |
| mastery_table.rows | array | 数据行 |
| resource_usage_table | object | 资源使用习惯记录表 |
| resource_usage_table.columns | array | 表头列 |
| resource_usage_table.rows | array | 数据行 |
| summary_text | string | LLM 文字总结 |
| generated_at | string | 评估生成时间 |

### 6.2 刷新学习效果评估

```
POST /api/v1/evaluation/refresh
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |

**说明：** Backend 聚合练习记录、资源使用、学习路径进度、辅导对话摘要等 SQL 数据后异步调用 Agent 生成评估；完成后保存为该用户在该课程下的最近评估。

---

## 七、用户画像 `/api/v1/profile`

### 7.1 冷启动固定问卷

```
POST /api/v1/profile/initialize
```

**说明：** v1 开发阶段冷启动不做 Agent 多轮引导，前端展示固定问卷并提交答案；Backend 按 `user_id + course_id` 保存初始画像。画像刷新时再调用 Agent。

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| answers | object | 是 | 固定问卷答案 |
| answers.guidance_level | string | 否 | 期望引导粒度：L1 / L2 / L3 |
| answers.modal_preference | array | 否 | 偏好的学习形式，如 text / diagram / code / formula |
| answers.learning_goal | string | 否 | 学习目标，如 exam_sprint / daily_homework / casual |

**响应 `data`：**

返回初始画像数据，结构同 `GET /profile`。

### 7.2 获取用户画像

```
GET /api/v1/profile?course_id={course_id}
```

**说明：** 画像按 `user_id + course_id` 保存，本接口只读取最近一次画像，不触发 Agent 生成。若尚未初始化或刷新画像，返回默认空画像，前端可正常渲染空状态。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| course_id | string | 课程 ID |
| modal_preference | object | 模态偏好（五维雷达图） |
| modal_preference.video_animation | number | 视频动画偏好 0-100 |
| modal_preference.chart_logic | number | 图表逻辑偏好 0-100 |
| modal_preference.text_analysis | number | 文字解析偏好 0-100 |
| modal_preference.code_practice | number | 代码实践偏好 0-100 |
| modal_preference.formula_derivation | number | 公式推导偏好 0-100 |
| guidance_level | object | 引导粒度 |
| guidance_level.current | string | 当前级别：L1 / L2 / L3 |
| guidance_level.updated_at | string | 更新时间 |
| knowledge_coordinates | array | 知识坐标（已掌握+正在学，时间轴+标签） |
| knowledge_coordinates[].name | string | 知识点名称 |
| knowledge_coordinates[].status | string | 状态：mastered / learning |
| knowledge_coordinates[].mastered_at | string | 掌握时间（learning 时为 null） |
| cognitive_blindspots | array | 认知盲区（易错点标签） |
| cognitive_blindspots[].name | string | 知识点名称 |
| cognitive_blindspots[].error_count | integer | 错误次数 |
| cognitive_blindspots[].severity | string | 严重程度：high / medium / low |
| drive_intent | object | 驱动意图（状态光环） |
| drive_intent.type | string | 类型：exam_sprint / daily_homework / casual |
| drive_intent.intensity | number | 近期学习强度 0-100 |
| drive_intent.learning_goal | string | 学习目标，自然语言补充后可返回 |
| drive_intent.source | string | 来源标记，如 profile_dialogue |
| discipline_badge | object | 学科底座徽章 |
| discipline_badge.subject | string | 学科名称 |
| discipline_badge.level | string | 徽章等级 |
| discipline_badge.streak_days | integer | 连续学习天数 |
| profile_dimensions | array | 六维画像摘要，供前端直接渲染 |
| profile_dimensions[].key | string | 维度键：learning_goal / weak_points / resource_preference / guidance_level / knowledge_progress / discipline |
| profile_dimensions[].label | string | 维度展示名 |
| profile_dimensions[].value | any | 维度值，可能是字符串、数组、数字或对象 |
| profile_dimensions[].source | string | 维度来源：profile_dialogue / system_profile / resource_usage / evaluation / activity / system_pending |
| generated_at | string | 画像生成时间 |

### 7.3 对话补充用户画像

```
POST /api/v1/profile/dialogue-update
```

**说明：** 将学生自然语言补充的学习目标、薄弱点、资源偏好等信息提交给 Agent 解析，并合并到当前课程画像。Agent 解析失败时不覆盖已有画像。

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| message | string | 是 | 学生补充文本，1-1000 字符 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| profile | object | 本次从文本中解析出的画像增量 |
| sources | object | 本次增量字段来源，值为 profile_dialogue |
| profile_data | object | 合并后的完整画像，结构同 `GET /profile` |

### 7.4 刷新用户画像

```
POST /api/v1/profile/refresh
```

**说明：** 根据最近的学习效果评估、练习、辅导对话、资源使用等数据异步调用 Agent 生成新画像，完成后覆盖该用户在该课程下的最近画像。

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |

---

## 八、学习路径 `/api/v1/learning-path`

### 8.1 获取学习路径

```
GET /api/v1/learning-path?course_id={course_id}
```

**说明：** 本接口只读取当前用户在该课程下最近一次学习路径，不实时调用 Agent。若尚未生成路径，返回 `nodes: []`、`edges: []`、`current_position: null`、`generated_at: null`，前端展示空状态或引导刷新。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| course_id | string | 课程 ID |
| nodes | array | 路径节点列表 |
| nodes[].id | string | 节点 ID |
| nodes[].name | string | 知识点名称 |
| nodes[].status | string | 完成状态：completed / in_progress / pending / recommended |
| nodes[].mastery | number | 掌握度 0-100 |
| nodes[].order | integer | 排序序号 |
| nodes[].reason | string | 推荐或排序原因 |
| edges | array | 节点间依赖边 |
| edges[].from | string | 前置节点 ID |
| edges[].to | string | 后置节点 ID |
| current_position | object | 当前学习位置 |
| current_position.node_id | string | 当前节点 ID |
| current_position.node_name | string | 当前节点名称 |
| generated_at | string | 路径生成时间 |

### 8.2 刷新学习路径

```
POST /api/v1/learning-path/refresh
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |

**说明：** Backend 读取该课程的静态知识图谱、最近学习效果评估和用户画像后异步调用 Agent。知识图谱决定可学习节点和前置依赖顺序，Agent 只负责个性化排序、推荐理由和当前节点建议，不允许脱离课程知识图谱自由编排路径。

### 8.3 节点资源推送

```
GET /api/v1/learning-path/nodes/:node_id/resources
```

**说明：** 根据当前路径节点关联的知识点查询资源和练习。若资源不足，返回空数组，不视为错误。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID，用于限定资源查询范围和课程权限校验 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| node_id | string | 节点 ID |
| node_name | string | 知识点名称 |
| weak_point_tutorials | array | 薄弱知识点讲解 |
| weak_point_tutorials[].id | string | 资源 ID，可跳转 `/resource/:id` |
| weak_point_tutorials[].title | string | 讲解标题 |
| weak_point_tutorials[].content | string | 正文摘要，不承载完整正文；Backend 仅返回前若干字符预览 |
| exercises | array | 配套习题 |
| exercises[].id | string | 题目 ID |
| exercises[].type | string | 题型：single_choice / multi_choice / code / short_answer |
| exercises[].content | string | 题目内容 |
| chapter_materials | array | 章节完整资料 |
| chapter_materials[].id | string | 资源 ID，可跳转 `/resource/:id` |
| chapter_materials[].title | string | 资料标题 |
| chapter_materials[].type | string | 类型：document / mindmap / reading / code |
| chapter_materials[].url | string | 资源链接 |
| full_exercise_set | array | 成套习题 |
| full_exercise_set[].id | string | 题目 ID |
| full_exercise_set[].type | string | 题型 |
| full_exercise_set[].content | string | 题目内容 |

**页面消费语义：**

- 本接口用于 LearningPath 底部资源面板的轻量挂载信息，不作为资源正文详情接口。
- 需要展示完整正文时，前端应根据资源 `id` 跳转 `GET /api/v1/resources/:id`。

**空态语义：**

- `weak_point_tutorials: []`、`exercises: []`、`chapter_materials: []`、`full_exercise_set: []` 均表示该节点当前没有可返回内容，不视为错误。

---

## 九、练习 `/api/v1/quiz`

**题目来源约定：**

- 题库由通用题和个性化题组成。
- 通用题面向课程/章节/知识点，所有加入该课程的学生可使用。
- 个性化题按 `owner_user_id` 归属当前学生，只对该学生可见。
- Agent 不直接写数据库；当前前端契约不提供触发 `/quiz/generate` 的页面入口，历史生题链路如需恢复必须重新进行产品契约审查。
- 支持题型固定为：`single_choice` / `multi_choice` / `code` / `short_answer`。

### 9.1 获取题目组

```
GET /api/v1/quiz/questions?course_id={course_id}&chapter={chapter}&knowledge_point={knowledge_point}
```

**说明：** 本接口只从题库取题，不实时调用 Agent。返回通用题和当前用户自己的个性化题；若题目不足或为空，返回空数组。当前前端契约不提供触发 `/quiz/generate` 的入口。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| chapter | string | 否 | 指定章节，为空则按当前进度出题 |
| knowledge_point | string | 否 | 指定知识点 |
| type | string | 否 | 题型：single_choice / multi_choice / code / short_answer |
| source | string | 否 | 题目来源：common / personalized |
| limit | integer | 否 | 返回题数，默认 10 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| quiz_id | string | 本次练习 ID（提交时回传） |
| course_id | string | 课程 ID |
| chapter | string | 章节 |
| questions | array | 题目列表 |
| questions[].id | string | 题目 ID |
| questions[].type | string | 题型：single_choice / multi_choice / code / short_answer |
| questions[].source | string | 来源：common / personalized |
| questions[].personalized | boolean | 是否个性化题 |
| questions[].content | string | 题目内容 |
| questions[].options | array | 选项列表（非选择题时为空数组 `[]`） |
| questions[].options[].key | string | 选项标识（A/B/C/D） |
| questions[].options[].text | string | 选项文本 |
| total_count | integer | 总题数 |

### 9.2 生成个性化题目（Deprecated / 前端作废不接入）

```
POST /api/v1/quiz/generate
```

**前端契约状态：** Deprecated。当前前端页面不应调用本接口，练习页不提供触发生题入口；如未来恢复生题产品链路，必须先重新完成产品契约审查。

**历史说明：** Backend 根据课程知识库、最近学习效果评估、用户画像、历史错题、当前学习路径节点等上下文调用 Agent 生题；Agent 返回结构化题目，Backend 校验后写入 `quiz_questions`。

**CourseCatalog ready gate：**

Backend 会先根据教学班 `course_id` 解析绑定的 `CourseOffering.catalog_id`，再检查对应 `CourseCatalog`：

- `status=ready` 且 `knowledge_status=ready`，允许生成；
- `status=ready` 且 `knowledge_status=partial` 且 `chunk_count>0`，允许降级生成；
- `knowledge_status=dirty/draft/failed/ingesting`，拒绝生成；
- `chunk_count<=0`，拒绝生成。

拒绝发生在创建异步任务前，因此不会返回 `task_id`。

错误：

- `404 course_catalog_missing`：课程未绑定可用资源库；
- `409 course_material_missing`：课程资料尚未完成入库；
- `409 knowledge_base_empty`：课程知识库为空。


**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| chapter | string | 否 | 章节 |
| knowledge_point | string | 否 | 知识点 |
| question_types | array | 否 | 题型列表：single_choice / multi_choice / code / short_answer |
| count | integer | 否 | 生成题数，默认 5 |
| difficulty | string | 否 | 难度：easy / medium / hard |
| personalized | boolean | 否 | 是否按当前学生个性化生成，默认 true |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |

### 9.3 提交答案

```
POST /api/v1/quiz/submit
```

**两步流程：**

1. **立即返回**：Backend 对选择题在 SQL 中对比正确答案，直接返回对错和耗时
2. **主观评估**：`code` / `short_answer` 可由 Backend 调用 Agent 评估；v1 可先同步评估或返回待诊断状态
3. **异步诊断**：Backend 后台调用 `POST /agent/v1/assessment/evaluate` 生成 LLM 诊断
4. **前端轮询**：`GET /api/v1/quiz/result` 获取诊断建议（诊断未完成时 `diagnosis` 为 null）

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| quiz_id | string | 是 | 练习 ID |
| answers | array | 是 | 答案列表 |
| answers[].question_id | string | 是 | 题目 ID |
| answers[].answer | string/array | 是 | 答案内容（选择题为选项 key，多选为数组） |
| time_spent | integer | 是 | 答题总耗时（秒） |

**立即响应 `data`（Backend SQL 比对，~毫秒级）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| quiz_id | string | 练习 ID |
| score | number | 正确率 0-100 |
| correct_count | integer | 正确题数 |
| total_count | integer | 总题数 |
| time_spent | integer | 耗时（秒） |
| per_question_results | array | 每题结果 |
| per_question_results[].question_id | string | 题目 ID |
| per_question_results[].is_correct | boolean | 是否正确 |
| per_question_results[].correct_answer | string/array | 正确答案 |
| per_question_results[].explanation | string | 解析（初值为 null，LLM 异步生成后通过 GET /quiz/result 获取） |

### 9.4 练习结果与诊断

```
GET /api/v1/quiz/result?course_id={course_id}
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| course_id | string | 课程 ID |
| latest_quiz | object | 最近一次练习 |
| latest_quiz.quiz_id | string | 练习 ID |
| latest_quiz.score | number | 正确率 |
| latest_quiz.time_spent | integer | 耗时 |
| latest_quiz.created_at | string | 完成时间 |
| stats | object | 统计汇总 |
| stats.total_attempts | integer | 总练习次数 |
| stats.avg_score | number | 平均正确率 |
| stats.avg_time_spent | integer | 平均耗时（秒） |
| stats.score_trend | array | 正确率变化趋势 [{date, score}] |
| diagnosis | object | 智能诊断 |
| diagnosis.summary | string | 诊断总结 |
| diagnosis.weak_points | array | 薄弱知识点列表 |
| diagnosis.weak_points[].name | string | 知识点名称 |
| diagnosis.weak_points[].error_rate | number | 错误率 |
| diagnosis.suggestions | array | 复习建议 |

### 9.5 历史练习记录

```
GET /api/v1/quiz/history?course_id={course_id}&page=1&page_size=20
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| records | array | 练习记录列表 |
| records[].quiz_id | string | 练习 ID |
| records[].course_id | string | 课程 ID |
| records[].chapter | string | 章节 |
| records[].score | number | 正确率 |
| records[].time_spent | integer | 耗时 |
| records[].question_count | integer | 题数 |
| records[].created_at | string | 完成时间 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

---

## 十、资源库 `/api/v1/resources`

**资源类型约定：** 资源库只存学习资料，不承担练习题主链路。个性化题目生成、取题、判题统一走 `/api/v1/quiz`。v1 资源类型为：

- `document`：知识讲解文档，Markdown 内容。
- `mindmap`：思维导图，Mermaid / JSON / 文本结构。
- `reading`：拓展阅读材料，Markdown 内容。
- `code`：代码示例，代码块 + 解释 + 复杂度/常见问题。
- `video`：预留类型，v1 默认不生成或返回视频内容。

### 10.1 获取资源库

```
GET /api/v1/resources?course_id={course_id}&type={type}&page=1&page_size=20
```

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| type | string | 否 | 资源类型：document / mindmap / reading / code / video；video 为预留类型，v1 默认不生成或返回视频内容 |
| keyword | string | 否 | 标题关键词搜索 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| resources | array | 资源列表 |
| resources[].id | string | 资源 ID |
| resources[].title | string | 资源标题 |
| resources[].type | string | 资源类型：document / mindmap / reading / code / video；video 为预留类型，v1 默认不生成或返回视频内容 |
| resources[].description | string | 资源描述 |
| resources[].tags | array | 标签列表 |
| resources[].chapter | string | 所属章节 |
| resources[].knowledge_point | string | 关联知识点 |
| resources[].view_count | integer | 浏览次数 |
| resources[].created_at | string | 创建时间 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

### 10.2 获取资源详情

```
GET /api/v1/resources/:id
```

**说明：** 资源详情页使用该接口读取单条资源内容。`data` 结构为 `ResourceDetailItem`，即资源列表字段加 `content_preview` 和 `content`。

**路径参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 资源 ID |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 资源 ID |
| title | string | 资源标题 |
| type | string | 资源类型：document / mindmap / reading / code / video |
| description | string | 资源描述 |
| tags | array | 标签列表 |
| chapter | string | 所属章节 |
| knowledge_point | string | 关联知识点 |
| view_count | integer | 浏览次数 |
| created_at | string | 创建时间 |
| content_preview | string \| null | 正文预览；`document` / `reading` 返回文本预览，其余类型返回 `null` |
| content | string \| null | 资源正文内容；用于详情页按类型展示正文、代码或思维导图文本 |

**空态语义：**

- `content_preview: null` 表示该资源类型不提供文字正文预览，不代表资源不存在。
- `content: null` 或空字符串表示当前资源暂无可展示正文内容，前端应展示空态，不应伪造正文。
- 无权限访问返回 `403`，资源不存在返回 `404`，前端不应以空对象替代。

### 10.3 触发资源生成（Deprecated / 前端作废不接入）

```
POST /api/v1/resources/generate
```

**权限：** 仅 teacher（历史接口权限）

**前端契约状态：** Deprecated。当前前端页面不应调用本接口，教师端不提供生成资源入口；如未来恢复资源生成产品链路，必须先重新完成产品契约审查。

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| chapter | string | 否 | 章节 |
| knowledge_point | string | 否 | 知识点 |
| resource_types | array | 否 | 资源类型列表：document / mindmap / reading / code；不传则默认生成这四类 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |

**历史说明：** 资源生成为长时间异步任务，Agent 完成后通过 Webhook 回调。该接口曾用于生成课程级学习资料，不生成个性化题目。当前前端契约中 `/api/v1/resources/generate` 和 `/api/v1/quiz/generate` 均作废 / 不接入。

**CourseCatalog ready gate：**

Backend 会先根据教学班 `course_id` 解析绑定的 `CourseOffering.catalog_id`，再检查对应 `CourseCatalog`：

- `status=ready` 且 `knowledge_status=ready`，允许生成；
- `status=ready` 且 `knowledge_status=partial` 且 `chunk_count>0`，允许降级生成；
- `knowledge_status=dirty/draft/failed/ingesting`，拒绝生成；
- `chunk_count<=0`，拒绝生成。

拒绝发生在创建异步任务前，因此不会返回 `task_id`。

错误：

- `404 course_catalog_missing`：课程未绑定可用资源库；
- `409 course_material_missing`：课程资料尚未完成入库；
- `409 knowledge_base_empty`：课程知识库为空。


---

## 十一、智能辅导 `/api/v1/tutoring`

**模式约定：**

- `course`：课程内智能辅导，必须传 `course_id`，Agent 使用课程知识库 RAG、用户画像、长期记忆回答。
- `global`：全局智能辅导，不传 `course_id`，作为简单 AI Bot 使用；不读取课程知识库，只使用通用能力和用户长期记忆。
- 教师不能查看学生智能辅导对话；对话历史仅当前登录用户本人可见。
- Backend 全量保存用户与助手对话消息，并为每条消息补充 meta 信息；记忆压缩只生成摘要和事实，不替代原始对话存储。
- 每次回复前，Agent Service 都会检索用户长期记忆和相关历史事实，再结合 Backend 传入的最近消息生成回复。

### 11.1 发起对话

```
POST /api/v1/tutoring/chat
```

**响应 Content-Type:** `text/event-stream` (SSE)

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户消息 |
| scope | string | 否 | 对话范围：course / global，默认 course |
| course_id | string | 条件必填 | 课程上下文 ID；scope=course 时必填，scope=global 时为空 |
| conversation_id | string | 否 | 继续已有对话时传入；为空则创建新对话 |

**消息存储：** Backend 保存完整 user/assistant 消息，不只保存摘要。每条消息建议记录 `meta`：`scope`、`course_id`、`knowledge_points`、`model_name`、`token_count`、`safety_flags`、`created_at` 等。

**SSE 事件类型：**

| type | 说明 |
|------|------|
| chunk | 文本片段 |
| diagram | 图解（Mermaid 语法或图表 JSON） |
| knowledge_points | 引用的知识点列表 |
| suggestion | 补充学习建议 + 相似例题推送 |
| done | 本轮回答完成，携带 conversation_id |

**`done` 事件 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| conversation_id | string | 对话 ID（新对话时返回） |
| message_id | string | 本条回复的消息 ID |

### 11.2 对话历史列表

```
GET /api/v1/tutoring/conversations?scope={scope}&course_id={course_id}&page=1&page_size=20
```

**说明：** 仅返回当前登录用户自己的对话。教师不可通过该接口查看学生对话。

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| scope | string | 否 | course / global |
| course_id | string | 否 | 课程 ID；筛选课程内对话 |
| page | integer | 否 | 页码，默认 1 |
| page_size | integer | 否 | 每页条数，默认 20 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| conversations | array | 对话列表 |
| conversations[].id | string | 对话 ID |
| conversations[].scope | string | course / global |
| conversations[].course_id | string | 课程 ID，全局对话为 null |
| conversations[].title | string | 对话标题（首条消息摘要） |
| conversations[].last_message | string | 最后一条消息摘要 |
| conversations[].message_count | integer | 消息数 |
| conversations[].updated_at | string | 最后更新时间 |

分页字段位于 `data` 内：`total`, `page`, `page_size`

### 11.3 对话历史详情

```
GET /api/v1/tutoring/conversations/:id
```

**说明：** 仅当前登录用户本人可查看该对话详情；教师不可查看学生对话。

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 对话 ID |
| scope | string | course / global |
| course_id | string | 课程 ID，全局对话为 null |
| title | string | 对话标题 |
| messages | array | 消息列表 |
| messages[].role | string | 角色：user / assistant |
| messages[].content | string | 消息内容 |
| messages[].diagrams | array | 内嵌图解（如有） |
| messages[].knowledge_points | array | 引用的知识点 |
| messages[].meta | object | 消息元信息，如模型、token、检索命中、安全标记 |
| messages[].timestamp | string | 消息时间 |
| created_at | string | 对话创建时间 |
| updated_at | string | 最后更新时间 |

---

## 十二、通用 `/api/v1/tasks`

### 12.1 查询异步任务状态

**功能是干啥的：** 给前端轮询异步任务是否完成。当前前端已接入的主要场景包括 Admin CourseCatalog 入库、刷新画像、生成路径、刷新评估等；前端不直接感知 Agent webhook。

**功能实现方法：**

- 所有异步入口先在 Backend 创建任务记录，再返回 `task_id`。
- 前端每 1-3 秒轮询一次；`processing` 继续等，`completed` 后跳转或重新调用业务 GET，`failed` 显示错误。
- Backend 查询任务表时必须带上当前登录用户校验归属；无权访问按 404 处理。
- `course_catalog_ingestion` 完成后前端刷新资料列表和知识库状态。
- `kg_generation` 完成后前端刷新课程资源库知识图谱状态。
- `evaluation_refresh` / `profile_refresh` / `learning_path_refresh` 完成后通过 `result.updated_at` 表示已写入最新快照，前端再调用对应 GET 读取最新结果。
- `resource_generation` / `quiz_generation` 为历史生成任务类型；当前前端契约不提供对应触发入口。

```
GET /api/v1/tasks/:task_id
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务 ID |
| task_type | string | 任务类型：evaluation_refresh / profile_refresh / learning_path_refresh / kg_generation / quiz_generation / resource_generation / course_catalog_ingestion |
| status | string | 状态：processing / completed / failed |
| progress | integer | 进度百分比 0-100（部分任务支持） |
| result | object | 任务结果摘要（completed 时有值） |
| result.resource_ids | array | `resource_generation` 完成后可返回新资源 ID 列表 |
| result.question_ids | array | `quiz_generation` 完成后可返回新题目 ID 列表 |
| result.updated_at | string | `evaluation_refresh` / `profile_refresh` / `learning_path_refresh` 完成后可返回更新时间；前端再调用对应 GET 读取最新结果 |
| result.graph_id | string | `kg_generation` 完成后可返回新 KG ID |
| result.version | integer | `kg_generation` 完成后可返回新 KG 版本 |
| result.node_count | integer | `kg_generation` 完成后可返回节点数 |
| result.edge_count | integer | `kg_generation` 完成后可返回边数 |
| error_code | string | 错误码（failed 时可选） |
| error_message | string | 错误信息（failed 时有值） |
| created_at | string | 创建时间 |
| completed_at | string | 完成时间（未完成时为 null） |

**权限说明：** 需要用户 JWT。普通用户只能查询自己触发的任务；教师只能查询自己触发的课程资源生成任务。不存在或无权访问统一返回 404，避免暴露他人任务 ID。

---

## 十三、Webhook 回调 `/api/v1/webhooks`

### 13.1 Agent 异步任务回调

**功能是干啥的：** 这是 Agent Service 通知 Backend“长任务完成/失败”的内部入口。前端不调用，也不会等待这个 webhook。

**功能实现方法：**

- Backend 调用 Agent 前先创建本地任务，并把同一个 `task_id` 传给 Agent。
- Agent 完成后 POST 到 `webhook_url`，携带 `task_id`、`task_type`、`status` 和结果。
- Backend 根据 `task_id` 找任务，校验任务存在、类型一致、当前不是已完成状态。
- `completed` 时 Backend 校验 `result` 结构，写入业务表，再把任务改为 `completed`。
- `failed` 时只更新任务失败状态和错误信息。
- 重复回调必须幂等处理：已完成任务再次收到 `completed` 时直接返回 success，不重复插入业务数据。

```
POST /api/v1/webhooks/agent
```

**无需用户 JWT；仅供内部 Agent Service 回调。** v1 无需额外鉴权，部署时通过内网地址或容器网络限制访问即可。

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| task_type | string | 是 | 任务类型，v1 主要为 `resource_generation` |
| status | string | 是 | 状态：completed / failed |
| result | object | 否 | 任务结果（completed 时必填） |
| error_message | string | 否 | 错误信息（failed 时必填） |

**响应 `data`：** `{}`

**处理规则：**

- Backend 根据 `task_id` 查询本地任务记录，校验 `task_type` 是否一致。
- `completed` 时由 Backend 校验 `result` 结构并写入 SQL，例如资源生成写入 `resources` 表。
- `failed` 时 Backend 写入失败状态和 `error_message`。
- 回调按 `task_id + status` 幂等处理；重复收到同一完成回调时不重复写入业务数据。
- Agent Service 不直接写 Backend 数据库。
