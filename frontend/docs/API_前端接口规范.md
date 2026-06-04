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
{ "code": 200, "message": "success", "data": [...], "total": 142, "page": 1, "page_size": 20 }

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

JWT Bearer Token，登录后获取。Header: `Authorization: Bearer <access_token>`

- `access_token` 有效期 30 分钟
- `refresh_token` 有效期 7 天
- access_token 过期后用 `/auth/refresh` 刷新
- 带 ~~删除线~~ 的端点无需认证

### 流式响应 (SSE)

`Content-Type: text/event-stream`，每条消息格式：

```
data: {"type": "chunk", "content": "你好，这道题考察的是..."}
data: {"type": "tool_call", "tool": "diagram", "data": "graph TD; A-->B"}
data: {"type": "done", "conversation_id": "conv_xxx"}
```

### 异步任务

刷新/生成类接口返回 `{task_id}` + HTTP 202，前端通过 `GET /api/v1/tasks/:task_id` 轮询状态。

```
POST /xxx/refresh → 202 { task_id }
GET  /tasks/:task_id → 200 { status: "processing" } 或 { status: "completed", result: {...} }
```

---

## 一、认证 `/api/v1/auth`

### 1.1 获取验证码

```
GET /api/v1/auth/captcha
```

**无需认证**

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| captcha_token | string | 验证码标识，登录时回传 |
| captcha_question | string | 数学算式（如 "3 + 5 = ?"） |

### 1.2 注册

```
POST /api/v1/auth/register
```

**无需认证**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| registration_code | string | 是 | 注册码，区分角色（如 "teacher"、"student"） |
| email | string | 是 | 邮箱地址 |
| password | string | 是 | 密码（8-32 位，含大小写字母+数字） |
| username | string | 是 | 用户名（3-20 位） |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 ID |
| email | string | 邮箱 |
| username | string | 用户名 |

**错误码：**

| code | 说明 |
|------|------|
| 40001 | 注册码无效或已被使用 |
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
| access_token | string | JWT 访问令牌 |
| refresh_token | string | JWT 刷新令牌 |
| expires_in | integer | access_token 有效期（秒），默认 1800 |
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

### 1.4 刷新 Token

```
POST /api/v1/auth/refresh
```

**无需认证**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| refresh_token | string | 是 | 登录时获取的 refresh_token |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | string | 新的 JWT 访问令牌 |
| expires_in | integer | 有效期（秒） |

**错误码：**

| code | 说明 |
|------|------|
| 40101 | refresh_token 无效或已过期 |

### 1.5 发送重置密码验证码

```
POST /api/v1/auth/send-reset-code
```

**无需认证**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 注册邮箱 |

**响应 `data`：** `{}`

**说明：** 邮件发送成功即返回 200，不暴露邮箱是否已注册

### 1.6 重置密码

```
POST /api/v1/auth/reset-password
```

**无需认证**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 注册邮箱 |
| reset_code | string | 是 | 邮箱收到的验证码 |
| new_password | string | 是 | 新密码（8-32 位） |

**响应 `data`：** `{}`

**错误码：**

| code | 说明 |
|------|------|
| 40003 | 验证码错误或过期 |

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
| courses | array | 已选课程列表（学生）或 开课列表（教师） |
| courses[].course_id | string | 课程 ID |
| courses[].course_name | string | 课程名称 |
| courses[].course_code | string | 课程码 |
| created_at | string | 创建时间 ISO 8601 |

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

**说明：** email、role 不可通过此接口修改。课程不可通过此接口修改（走 `/courses` 域）。

**响应 `data`：** 同 `GET /users/me` 的完整个人信息

---

## 三、课程 `/api/v1/courses`

### 3.1 我的课程列表

```
GET /api/v1/courses
```

**说明：** 教师返回自己开的班，学生返回自己加入的班

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

### 4.1 班级学生列表

```
GET /api/v1/teaching/classes/:class_id/students
```

**权限：** 仅该班级的教师

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

分页字段：`total`, `page`, `page_size`

### 4.2 查看学生个人信息

```
GET /api/v1/teaching/classes/:class_id/students/:student_id
```

**权限：** 仅该班级的教师

**响应 `data`：** 与 `GET /users/me` 结构完全一致

### 4.3 查看学生学习情况

```
GET /api/v1/teaching/classes/:class_id/students/:student_id/learning
```

**权限：** 仅该班级的教师

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
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

分页字段：`total`, `page`, `page_size`

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
| password | string | 否 | 重置密码（提供则覆盖旧密码） |

**响应 `data`：** 更新后的用户完整信息

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

分页字段：`total`, `page`, `page_size`

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
| logs[].detail | object | 事件详细数据 |

分页字段：`total`, `page`, `page_size`

---

## 六、学习效果评估 `/api/v1/evaluation`

### 6.1 获取学习效果评估

```
GET /api/v1/evaluation?course_id={course_id}
```

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

---

## 七、用户画像 `/api/v1/profile`

### 7.1 冷启动引导对话

```
POST /api/v1/profile/initialize
```

**Content-Type:** `text/event-stream` (SSE)

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |

**SSE 事件类型：**

| type | 说明 |
|------|------|
| message | Agent 引导提问文本 |
| chunk | 流式文本片段 |
| done | 引导完成，携带初始画像数据 |

### 7.2 获取用户画像

```
GET /api/v1/profile?course_id={course_id}
```

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
| discipline_badge | object | 学科底座徽章 |
| discipline_badge.subject | string | 学科名称 |
| discipline_badge.level | string | 徽章等级 |
| discipline_badge.streak_days | integer | 连续学习天数 |
| generated_at | string | 画像生成时间 |

### 7.3 刷新用户画像

```
POST /api/v1/profile/refresh
```

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

### 8.3 节点资源推送

```
GET /api/v1/learning-path/nodes/:node_id/resources
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| node_id | string | 节点 ID |
| node_name | string | 知识点名称 |
| weak_point_tutorials | array | 薄弱知识点讲解 |
| weak_point_tutorials[].title | string | 讲解标题 |
| weak_point_tutorials[].content | string | 讲解内容 |
| exercises | array | 配套习题 |
| exercises[].id | string | 题目 ID |
| exercises[].type | string | 题型：single_choice / multi_choice / code / short_answer |
| exercises[].content | string | 题目内容 |
| chapter_materials | array | 章节完整资料 |
| chapter_materials[].title | string | 资料标题 |
| chapter_materials[].type | string | 类型：document / mindmap / slides / reading |
| chapter_materials[].url | string | 资源链接 |
| full_exercise_set | array | 成套习题 |
| full_exercise_set[].id | string | 题目 ID |
| full_exercise_set[].type | string | 题型 |
| full_exercise_set[].content | string | 题目内容 |

---

## 九、练习 `/api/v1/quiz`

### 9.1 获取题目组

```
GET /api/v1/quiz/questions?course_id={course_id}&chapter={chapter}
```

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| chapter | string | 否 | 指定章节，为空则按当前进度出题 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| quiz_id | string | 本次练习 ID（提交时回传） |
| course_id | string | 课程 ID |
| chapter | string | 章节 |
| questions | array | 题目列表 |
| questions[].id | string | 题目 ID |
| questions[].type | string | 题型：single_choice / multi_choice / code / short_answer |
| questions[].content | string | 题目内容 |
| questions[].options | array | 选项列表（非选择题时为 null） |
| questions[].options[].key | string | 选项标识（A/B/C/D） |
| questions[].options[].text | string | 选项文本 |
| total_count | integer | 总题数 |

### 9.2 提交答案

```
POST /api/v1/quiz/submit
```

**两步流程：**

1. **立即返回**：Backend 在 SQL 中对比正确答案，直接返回对错和耗时（毫秒级，无需等 Agent）
2. **异步诊断**：Backend 后台调用 `POST /agent/v1/assessment/evaluate` 生成 LLM 诊断
3. **前端轮询**：`GET /api/v1/quiz/result` 获取诊断建议（诊断未完成时 `diagnosis` 为 null）

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
| per_question_results[].correct_answer | string | 正确答案 |
| per_question_results[].explanation | string | 解析（初值为 null，LLM 异步生成后通过 GET /quiz/result 获取） |

### 9.3 练习结果与诊断

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

### 9.4 历史练习记录

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

分页字段：`total`, `page`, `page_size`

---

## 十、资源库 `/api/v1/resources`

### 10.1 获取资源库

```
GET /api/v1/resources?course_id={course_id}&type={type}&page=1&page_size=20
```

**查询参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |
| type | string | 否 | 资源类型：document / mindmap / exercise / reading / code |
| keyword | string | 否 | 标题关键词搜索 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| resources | array | 资源列表 |
| resources[].id | string | 资源 ID |
| resources[].title | string | 资源标题 |
| resources[].type | string | 资源类型 |
| resources[].description | string | 资源描述 |
| resources[].tags | array | 标签列表 |
| resources[].chapter | string | 所属章节 |
| resources[].view_count | integer | 浏览次数 |
| resources[].created_at | string | 创建时间 |

分页字段：`total`, `page`, `page_size`

### 10.2 触发资源生成

```
POST /api/v1/resources/generate
```

**权限：** 仅 teacher

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| course_id | string | 是 | 课程 ID |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |

**说明：** 资源生成为长时间异步任务，Agent 完成后通过 Webhook 回调

---

## 十一、智能辅导 `/api/v1/tutoring`

### 11.1 发起对话

```
POST /api/v1/tutoring/chat
```

**Content-Type:** `text/event-stream` (SSE)

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户消息 |
| course_id | string | 否 | 课程上下文 ID |
| conversation_id | string | 否 | 继续已有对话时传入；为空则创建新对话 |

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
GET /api/v1/tutoring/conversations?page=1&page_size=20
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| conversations | array | 对话列表 |
| conversations[].id | string | 对话 ID |
| conversations[].title | string | 对话标题（首条消息摘要） |
| conversations[].last_message | string | 最后一条消息摘要 |
| conversations[].message_count | integer | 消息数 |
| conversations[].updated_at | string | 最后更新时间 |

分页字段：`total`, `page`, `page_size`

### 11.3 对话历史详情

```
GET /api/v1/tutoring/conversations/:id
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 对话 ID |
| title | string | 对话标题 |
| messages | array | 消息列表 |
| messages[].role | string | 角色：user / assistant |
| messages[].content | string | 消息内容 |
| messages[].diagrams | array | 内嵌图解（如有） |
| messages[].knowledge_points | array | 引用的知识点 |
| messages[].timestamp | string | 消息时间 |
| created_at | string | 对话创建时间 |
| updated_at | string | 最后更新时间 |

---

## 十二、通用 `/api/v1/tasks`

### 12.1 查询异步任务状态

```
GET /api/v1/tasks/:task_id
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务 ID |
| task_type | string | 任务类型：evaluation / profile / learning_path / resource / memory_compress |
| status | string | 状态：processing / completed / failed |
| progress | integer | 进度百分比 0-100（部分任务支持） |
| result | object | 任务结果（completed 时有值） |
| error_message | string | 错误信息（failed 时有值） |
| created_at | string | 创建时间 |
| completed_at | string | 完成时间（未完成时为 null） |

---

## 十三、Webhook 回调 `/api/v1/webhooks`

### 13.1 Agent 异步任务回调

```
POST /api/v1/webhooks/agent
```

**无需认证（服务间调用，内部密钥校验）**

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| task_type | string | 是 | 任务类型 |
| status | string | 是 | 状态：completed / failed |
| result | object | 否 | 任务结果（completed 时必填） |
| error_message | string | 否 | 错误信息（failed 时必填） |

**响应 `data`：** `{}`
