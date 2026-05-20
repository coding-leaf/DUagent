# API 文档一致性分析报告

> 基准：以 `API_前端接口规范.md` 和 `API_Agent内部接口规范.md` 为准
> 对比对象：`Client-API.openapi.json` 和 `Agent-Service.openapi.json`
> 分析日期：2026-05-17

---

## 一、Client-API（前端 <-> 后端）

### 1. 认证模块 — 无问题

---

### 2. 用户信息

#### 2.1 GET /api/v1/user/info — Response schema 缺失字段

| 严重度 | 问题 |
|--------|------|
| **HIGH** | `data.username` 和 `data.email` 在 JSON schema 中缺失。MD 明确定义了这两个字段，JSON 的 required 只有 `user_id, role, profile, current_path_node` |
| **HIGH** | `profile.modality_preference` 的 required 数组缺少 `video`。MD 定义五维雷达图包含 video/chart/text/code/formula 五项，JSON 的 required 只有 `["chart","text","code","formula"]` |

#### 2.2 PUT /api/v1/user/guidance-level — 请求方式错误

| 严重度 | 问题 |
|--------|------|
| **CRITICAL** | MD 定义为 **request body** 传参 `{ "guidance_level": "L1" }`，但 JSON 把 `guidance_level` 写成了 **query parameter**，且完全缺少 requestBody 定义 |

```diff
- JSON 当前: PUT /api/v1/user/guidance-level?guidance_level=L1
+ 应为:     PUT /api/v1/user/guidance-level  + Body {"guidance_level":"L1"}
```

---

### 3. 智能对话

#### 3.1 POST /api/v1/chat/completions — SSE 数据格式不一致

| 严重度 | 问题 |
|--------|------|
| **HIGH** | MD 定义的 SSE data 格式为 `{"type":"status","content":"..."}` ，但 JSON example 将其错误包裹在统一返回格式中：`{"code":200,"message":"success","data":{...}}`。应以 MD 为准——SSE 流内每条消息直接就是 `{type, content}` |

```
MD 格式（正确）:
event: message
data: {"type": "status", "content": "正在检索知识库..."}

JSON 当前（错误）:
event: message
data: {"code": 200, "message": "success", "data": {"type": "status", "content": "正在检索..."}}
```

| **LOW** | `session_id` 标记为 required，但 MD 说明"首次对话可为空由后端生成" |

#### 3.2 GET /api/v1/chat/history — messages 类型错误

| 严重度 | 问题 |
|--------|------|
| **CRITICAL** | MD 定义 `messages` 为 **数组**，JSON 将其定义为 **object**（含 role/content/created_at 属性）。类型完全错误 |

```diff
- JSON 当前: "messages": { "type": "object", "properties": { "role":..., "content":..., "created_at":... } }
+ 应为:     "messages": { "type": "array", "items": { "type": "object", "properties": { "role":..., "content":..., "created_at":... } } }
```

#### 3.3 GET /api/v1/chat/sessions — data 类型错误

| 严重度 | 问题 |
|--------|------|
| **CRITICAL** | MD 定义 `data` 为 **数组（会话列表）**，JSON 将其定义为 **object（单个会话）** |

```diff
- JSON 当前: "data": { "type": "object", "properties": { "session_id":..., "title":..., "last_message_at":... } }
+ 应为:     "data": { "type": "array", "items": { "type": "object", "properties": { "session_id":..., "title":..., "last_message_at":... } } }
```

---

### 4. 测验评估

#### 4.1 GET /api/v1/assessment/quiz — options 必填性过严

| 严重度 | 问题 |
|--------|------|
| **HIGH** | JSON 将 `options` 设为所有题目的 required 字段。但 MD 明确：`options` 仅 `single_choice` 和 `multi_choice` 题型有此字段。`true_false` / `fill_blank` / `code` / `short_answer` 不应出现 options |

```diff
- JSON 当前: questions[].required = ["id", "type", "question", "options"]
+ 应为:     questions[].required = ["id", "type", "question"]  // options 按题型可选
```

#### 4.2 POST /api/v1/assessment/submit — answers 硬编码

| 严重度 | 问题 |
|--------|------|
| **MEDIUM** | JSON 将 `answers` 硬编码为 q1~q6 固定属性，MD 定义为动态 key（`{"[q_id]": "答案"}`）。建议用 `additionalProperties` |

---

### 5. 学习效果评估 — 无问题

### 6. 推荐与路径 — 无问题

---

### 7. 资源生成与浏览

#### 7.2 GET /api/v1/resource/task/{task_id} — GET 不应有 requestBody

| 严重度 | 问题 |
|--------|------|
| **CRITICAL** | 此 GET 端点 JSON 中错误定义了 `requestBody`（content-type: application/x-www-form-urlencoded）。MD 无此定义，GET 请求不应有 body |

#### 7.3 GET /api/v1/resource/{source_id} — 参数命名

| 严重度 | 问题 |
|--------|------|
| **LOW** | 路径参数名为 `source_id`，但 MD 示例使用 `resource_id`（URL: `/api/v1/resource/res_101`） |

---

### 8. 课程与班级管理 — 无问题

### 9. 系统管理 — 无问题（注册码接口已标记 deprecated）

---

### 10. Webhook

#### 10.1 POST /internal/webhook/resource_completed — 缺少 requestBody

| 严重度 | 问题 |
|--------|------|
| **HIGH** | MD 明确定义了 Agent 回调的完整 request body（含 task_id, status, generated_resources 及 5 种资源子结构），但 JSON 中该端点无 requestBody 定义，responses schema 也为空 |

MD 定义的回调体（应补入 JSON）：
```json
{
  "task_id": "task_8848",
  "status": "success",
  "generated_resources": {
    "explanation_doc":   { "title": "...", "content_md": "..." },
    "mindmap":           { "title": "...", "mermaid_code": "..." },
    "quiz":              [{ "question": "...", "options": {}, "answer": "B", "explanation": "..." }],
    "extended_reading":  { "title": "...", "content_md": "..." },
    "code_practice":     { "title": "...", "language": "python", "code": "...", "explanation": "..." }
  }
}
```

---

## 二、Agent-Service（后端 <-> Agent）

### 1. POST /agent/v1/chat — 无问题（SSE 格式与 MD 一致）

### 2. POST /agent/v1/memory/compress — 无问题

---

### 3. POST /agent/v1/assessment/evaluate

#### 3.1 options 必填性过严

| 严重度 | 问题 |
|--------|------|
| **HIGH** | JSON 要求每道题 `options` 为 required 且固定 A/B/C。但不同题型 options 不同（判断题无 options、多选题选项数量可变）。应与 MD 对齐：options 非必填 |

#### 3.2 correct_answer 类型不完整

| 严重度 | 问题 |
|--------|------|
| **MEDIUM** | JSON 定义 `correct_answer` 仅为 string。但多选题正确答案是 array（如 `["A","C"]`），应支持 `string | array` |

---

### 4. POST /agent/v1/resource/generate

#### 4.1 Webhook callback URL 引用错误

| 严重度 | 问题 |
|--------|------|
| **MEDIUM** | Callback URL 使用 `{$request.body#/webhook_url}`，但 request body 中不存在 `webhook_url` 字段。MD 中 webhook 地址是固定值 `http://backend:8001/internal/webhook/resource_completed` |

#### 4.2 Callback requestBody 简化

| 严重度 | 问题 |
|--------|------|
| **LOW** | `generated_resources` 仅定义为 `"type": "object"`，未细化到 5 种资源类型的子 schema |

---

### 5. POST /agent/v1/profile/initialize — 无问题

### 6. POST /agent/v1/learning-path/plan — user_profile 为空

| 严重度 | 问题 |
|--------|------|
| **MEDIUM** | `user_profile` 定义为 `"properties": {}`，未文档化内部字段。MD 明确定义了 `guidance_level` 和 `discipline_base` |

---

## 三、汇总

### CRITICAL（阻塞实现 — 4项）

| # | 文件 | 端点 | 问题 |
|---|------|------|------|
| C1 | Client-API JSON | `PUT /api/v1/user/guidance-level` | 参数在 query 而非 body |
| C2 | Client-API JSON | `GET /api/v1/chat/history` | `messages` 类型 object 应为 array |
| C3 | Client-API JSON | `GET /api/v1/chat/sessions` | `data` 类型 object 应为 array |
| C4 | Client-API JSON | `GET /api/v1/resource/task/{task_id}` | GET 端点有 requestBody |

### HIGH（会导致前后端对接异常 — 5项）

| # | 文件 | 端点 | 问题 |
|---|------|------|------|
| H1 | Client-API JSON | `GET /api/v1/user/info` | 缺 username/email；modality_preference 缺 video |
| H2 | Client-API JSON | `POST /api/v1/chat/completions` | SSE data 多余外层 envelope |
| H3 | Client-API JSON | `GET /api/v1/assessment/quiz` | options 对所有题型强制 required |
| H4 | Client-API JSON | `POST /internal/webhook/resource_completed` | 无 requestBody schema |
| H5 | Agent-Service JSON | `POST /agent/v1/assessment/evaluate` | options 强制 required；correct_answer 不支持 array |

### MEDIUM（影响扩展性和完备性 — 3项）

| # | 文件 | 端点 | 问题 |
|---|------|------|------|
| M1 | Client-API JSON | `POST /api/v1/assessment/submit` | answers 硬编码 q1~q6 |
| M2 | Agent-Service JSON | `POST /agent/v1/resource/generate` | callback URL 引用不存在的字段 |
| M3 | Agent-Service JSON | `POST /agent/v1/learning-path/plan` | user_profile schema 为空 |

### LOW（命名/语义统一 — 3项）

| # | 问题 |
|---|------|
| L1 | `GET /api/v1/resource/{source_id}` 参数名应为 resource_id |
| L2 | `POST /api/v1/chat/completions` session_id 应 optional |
| L3 | Agent resource/generate callback generated_resources schema 过于简化 |

---

## 四、修复建议顺序

1. **先修 4 项 CRITICAL** — 不改则接口无法正常对接（类型错误会导致解析失败）
2. **再修 5 项 HIGH** — 不改则数据缺失或格式错误
3. **后修 3 项 MEDIUM** — 影响扩展性
4. **最后 3 项 LOW** — 命名统一
