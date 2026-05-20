# EduAgent - Agent Service 开发指南

**目标:** 专注于开发 Agent Service (Port 8002)，实现基于大模型的个性化学习业务逻辑，并直接与 Qdrant 向量库交互。
**开发模式:** 开发者主导，AI 辅助（Pair Programming）。

---

### 阶段 1: 基础架构与环境搭建
- **依赖:** `fastapi`, `uvicorn`, `qdrant-client`, `agentscope`, `sse-starlette`, `pydantic`
- **核心任务:**
  - 创建 `agent_service/requirements.txt` 并安装依赖。
  - 创建 `agent_service/main.py`: 初始化 FastAPI 实例、配置 CORS、添加 `/agent/v1/health` 健康检查接口。
  - 创建 `agent_service/core/qdrant.py`: 初始化 Qdrant 本地客户端，并在启动时确保 `course_knowledge` 和 `user_memory` 集合存在。
  - 搭建基础的目录结构 (如 `agents/`, `tools/`, `memory/`, `prompts/`, `models/`)。

### 阶段 2: 核心 Agent 业务逻辑实现
根据 `API_Agent内部接口规范.md`，逐步实现以下核心模块：
- **2.1 智能辅导 (Chat)**: `POST /agent/v1/tutoring/chat` (SSE流式输出，结合 Qdrant 检索)
- **2.2 用户画像 (Profile)**: `POST /agent/v1/profile/initialize` (冷启动引导对话，SSE流式)
- **2.3 测验评估 (Assessment)**: `POST /agent/v1/assessment/evaluate` (同步 JSON，评估对错与提取盲区)
- **2.4 资源生成 (Resources)**: `POST /agent/v1/resources/generate` (异步任务，Manager-Worker 模式，Webhook 回调)
- **2.5 记忆压缩 (Memory)**: `POST /agent/v1/memory/compress` (同步 JSON，提取事实存入 Qdrant)

### 阶段 3: 接口联调与测试
- 编写测试脚本或使用 Apifox 模拟 Backend 发送请求。
- 验证 SSE 流式输出的格式是否符合规范。
- 验证 Webhook 回调机制是否正常工作。
- 验证 Qdrant 向量检索的准确性和性能。
