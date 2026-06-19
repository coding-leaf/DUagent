# Spec: 环境变量清理与规范化

**日期**: 2026-06-20  
**分级**: 大改（跨模块环境整理，按规定先写 Spec）  
**影响模块**: frontend / backend / agent_service  

---

## 问题诊断

### 1. `backend/app/services/kg_generation.py` 绕过 settings 直读 os.environ

```python
# 文件: backend/app/services/kg_generation.py L53-54, L118-120
qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
collection  = os.environ.get("QDRANT_COURSE_KNOWLEDGE_COLLECTION", ...)
api_key  = os.environ.get("LLM_API_KEY") or settings.LLM_API_KEY
base_url = os.environ.get("LLM_BASE_URL") or settings.LLM_BASE_URL
model    = os.environ.get("LLM_MODEL") or settings.LLM_MODEL
```

**问题**：`settings` 对象（pydantic-settings）已经统一读取了 `.env`，再用 `os.environ.get` 是重复取值，且优先级逻辑（`or settings.XXX`）不一致。  
**尤其**：`QDRANT_URL`、`QDRANT_COURSE_KNOWLEDGE_COLLECTION` 用的是 backend settings，但这两个字段根本没有在 `backend/app/core/config.py` 里定义，是 agent_service 侧的配置！这是一个旁路调用的反模式。

### 2. `frontend/src/api/services/chat.js` 重复读 VITE_API_BASE_URL

```js
// chat.js L3-4
const useMock = import.meta.env.VITE_USE_MOCK === 'true';
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// chat.js L72
const url = `${apiBaseUrl}/tutoring/chat`;
```

**问题**：`VITE_API_BASE_URL` 已经在 `src/api/client.js` 里用于创建 axios 实例的 `baseURL`，chat.js 又拼了一遍，绕开了 axios 实例，直接用 `fetch`。这导致：
- `baseURL` 不统一（axios client 管大多数接口，chat.js 自行管 SSE 流式接口）
- 若 `VITE_API_BASE_URL` 改了，chat.js 必须同步改，有漂移风险

这是合理的技术分离（SSE 不能走 axios），但直接再读一遍环境变量而不复用 client 的 `baseURL` 不够优雅。**此项暂判为可接受，不强制改——改会引入副作用。**

### 3. `VITE_USE_MOCK` 散落三处

| 文件 | 用途 |
|------|------|
| `src/api/mock/index.js` | 控制 mock adapter 是否激活（正确） |
| `src/api/services/chat.js` | 声明了 `useMock` 变量，但在文件内从未分支使用（死代码） |
| `src/pages/TeacherConsole.jsx` | 读取后作为 prop 向下传递，用于显示"模拟模式"提示 |

**问题**：chat.js 里的 `useMock` 是死代码；TeacherConsole.jsx 直接读环境变量违反"只有入口/边界处读 env"的原则。

### 4. 缺少 `.env.example` 文件

| 模块 | 状态 |
|------|------|
| `agent_service/` | ✅ 有 `.env.example` |
| `backend/` | ❌ 缺失 |
| `frontend/` | ❌ 缺失 |

新开发者 clone 项目后不知道需要哪些环境变量。

### 5. 跨服务重复变量（共存，暂不合并）

`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`WEBHOOK_SECRET` 在 backend 和 agent_service 各有一份。  
这是由架构决定的**有意重复**——backend 独立连 LLM 做 KG 生成，agent_service 独立连 LLM 做对话，两者可以用不同的 model。  
**判断**：保留各自独立，不合并，通过 `.env.example` 说明清楚即可。

---

## 修复计划

### Step 1 — 修 `kg_generation.py`（backend，1 个文件）

**当前的问题**：  
kg_generation.py 使用 `QDRANT_URL` 和 `QDRANT_COURSE_KNOWLEDGE_COLLECTION`，这两个配置属于 agent_service 范畴，不在 backend settings 里。在 backend 内这个服务读 Qdrant 是合规的（backend-side KG 写入），但读配置的方式要统一。

**修改**：  
1. 在 `backend/app/core/config.py` 补充 Qdrant 相关字段（backend 与 agent 共享同一 Qdrant 实例，用相同默认值）  
2. `kg_generation.py` 改为全部通过 `settings.XXX` 读取，删除 `os.environ.get()`

```python
# config.py 新增字段
QDRANT_URL: str = "http://127.0.0.1:6333"
QDRANT_COURSE_KNOWLEDGE_COLLECTION: str = "course_knowledge_v1_1024"
```

注意：不在 backend `.env` 里加这两个字段，用默认值即可（与 agent_service 保持一致）。若生产环境需要不同值，再写入 .env。

### Step 2 — 删 chat.js 死代码（frontend，1 个文件）

删除 `chat.js` 第 3 行的 `const useMock = ...`，这个变量在文件内没有被使用。  
`VITE_API_BASE_URL` 那行保留（SSE 接口需要手拼 URL）。

### Step 3 — TeacherConsole.jsx 解耦 env（frontend，1 个文件）

TeacherConsole.jsx L20 直接读 env 不规范。有两种方案：

**方案 A**（推荐）：从 mock/index.js 导出状态  
```js
// mock/index.js 末尾新增
export const isMockEnabled = useMock;
```
TeacherConsole.jsx 改为 `import { isMockEnabled } from '../api/mock';` 取代 `import.meta.env`。

**方案 B**：在 `src/config.js` 集中导出所有 env 读取  
```js
// src/config.js  
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
```
所有 `import.meta.env` 访问收口到这一个文件。

**选方案 A**，更小改动，TeacherConsole 关心的就是 mock 是否激活，直接复用 mock/index.js 的判断。

### Step 4 — 补 `.env.example` 文件

**`backend/.env.example`**：
```
APP_NAME=DUagent API
APP_VERSION=5.0
DEBUG=true
DATABASE_URL=mysql+aiomysql://root:PASSWORD@localhost:3306/duagent?charset=utf8mb4
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
HOST=0.0.0.0
PORT=8001
AGENT_SERVICE_URL=http://localhost:8002
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
WEBHOOK_SECRET=your-shared-secret
CORS_ORIGINS=["http://localhost:5173"]
```

**`frontend/.env.example`**：
```
VITE_API_BASE_URL=http://localhost:8001/api/v1
VITE_USE_MOCK=false
```

---

## 执行顺序

1. Step 1：`backend/app/core/config.py` + `kg_generation.py`（1 commit）
2. Step 2：`frontend/src/api/services/chat.js`（1 commit）
3. Step 3：`frontend/src/api/mock/index.js` + `frontend/src/pages/TeacherConsole.jsx`（1 commit）
4. Step 4：补两个 `.env.example` 文件（1 commit）

每步完成后运行对应验证命令（见下）。

---

## 验证命令

```bash
# Step 1 — 后端语法检查
python3 -m py_compile backend/app/core/config.py
python3 -m py_compile backend/app/services/kg_generation.py

# Step 2-3 — 前端构建
cd frontend && npm run lint && npm run build

# 全步 — 快速冒烟
cd backend && python3 -m pytest tests/ -v -x 2>/dev/null | tail -5
```

---

## 不做的事（本次范围外）

- 合并 backend 和 agent_service 的 LLM 配置（架构上两者需独立）
- 修改 `chat.js` 的 SSE 实现（它绕 axios 用 fetch 是正常的，只删死代码）
- 任何 `.env` 密钥值的修改
- `COURSE_CATALOG_STORAGE_ROOT` 的统一（backend 和 agent_service 各自读自己的配置，路径恰好相同是现状，待专项处理）
