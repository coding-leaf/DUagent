# 阶段二：全栈架构重构与规范化 总规划 (Phase 2 Refactoring Guide)

本文件是后续 AI Agent 推进“阶段二架构重构”的**顶层指引（Framework）**。
AI 不需要被动等待用户指定修复哪个文件，而应当通过本指南中确立的**五大重构方向**，主动去代码库中扫描不合理的实现，并在产出专项 Spec 后自定实现方案。

---

## 五大重构方向与 AI 扫描判定标准

### 1. 整理目录 (Organize Directories)
**AI 扫描目标：**
- 找出动辄数百上千行、混合了不同职责的“胖文件”（Fat Files）。
- 特别关注后端 `backend/app/api/v1/` 下的大型路由文件（如 `catalogs.py` 65KB, `profile.py` 等）。
**动作指引：**
- 实施严格的分层设计：`Router (仅做入参出参处理) -> Service (业务逻辑编排/后台任务) -> DB`。
- 将背景任务（background tasks）从路由定义中剥离。
- 前端也需整理 `src/pages` 与 `src/components` 中耦合过深的视图。

### 2. 提取公共组件 (Extract Common Components)
**AI 扫描目标：**
- 找出多个文件或页面中被反复复制粘贴的代码块。
**动作指引：**
- **前端状态**：`AuthContext` / `ChatContext` / `CourseContext` 三者职责正交，**不合并**。扫描目标是：是否存在跨 Context 的重复状态字段，以及全局 Toast/Error 上下文是否缺失（当前 401 未触发跳转、各页面 `try-catch` 散落处理）。
- **UI 规范**：找出各页面中手写的重复 Tailwind 组件，提取到 `src/components/common`。
- **网络层**：提取标准的 Axios 请求层和全局的 401/403/500 异常拦截器，消灭各页面的无效 `try-catch` 重复逻辑。

### 3. 加测试 (Add Tests)
**AI 扫描目标：**
- 重构动作所影响到的关键核心链路。
**动作指引：**
- 在对模块（如后端的 Router 剥离出 Service）进行重构后，必须配套编写或调整对应的 Pytest 单元测试（后端）或 Playwright/Jest 测试（前端）。
- 确保测试覆盖新分离出去的纯逻辑代码，保障重构不会造成功能退化。

### 4. 清环境变量 (Clean Environment Variables)
**AI 扫描目标：**
- `frontend/.env`, `backend/.env`, `agent_service/.env` 中重复出现的配置项（例如多处出现同样的 `LLM_API_KEY`、`WEBHOOK_SECRET`）。
- 废弃或不在使用的过时变量。
- Python 项目的 `requirements.txt` 和 `uv.lock` 中未使用的依赖包，以及杂乱的虚拟环境。
**动作指引：**
- 提供统筹收口的环境变量加载机制或集中管理策略。
- 梳理配置文件，去除不需要的环境隔离。

### 5. 规范后端和 Agent 边界 (Standardize Backend & Agent Boundaries)
**背景：**
当前 `agent_service` 不连接 MySQL，无直接 CRUD，通过 Webhook 回调 Backend 写数据，边界**现状是清晰的**。

**AI 扫描目标：**
- 检查是否存在从 Agent 侧直接拼装发给前端”黑话”结构体（例如强绑定 `kg_node` 等）的现象。
- 扫描 `agent_service/api/` 中是否出现 `sqlalchemy` / 直接 DB 连接的新引入（防范滑坡）。

**动作指引：**
- **文档化契约**：在 `docs/superpowers/specs/` 输出一份 Backend ↔ Agent 通信方式说明（列出现有 Webhook 端点、SSE 链路、同步 HTTP 调用），固化现有边界，作为后续开发的约束基线。
- **防范性约束**：Agent 职责限定为”无状态推理计算”。所有持久化数据流必须经过 Backend 标准接口，禁止未来在 Agent 侧直接引入数据库操作。
- **数据清洗 (DTO)**：通过后端 Pydantic Schema 隔离层清洗 Agent 返回的内部字段，确保前端收到面向用户的纯业务数据。

---

## AI 自主推进流程 (AI Execution Flow)

1. **扫描与定位 (Analyze)**：AI 每次接到继续推进重构的命令时，自动根据这 5 大方向，全局检索 (`grep_search` / `list_dir`) 识别出当前最突出的 1 个违背规范的文件或模块。
2. **输出设计 (Plan)**：针对找到的具体痛点，在 `docs/superpowers/specs/` 下生成单一职责的 `YYYY-MM-DD-xxx-refactor-design.md`。在设计方案前，**主动判断是否需要引入下方附录中的系统架构或设计模式**（例如：是否需要过滤器/中间件链、是否应引入仓储层、是否适合用策略模式替换硬编码分支），并在 Spec 中说明选型理由。
3. **执行与测试 (Execute & Test)**：重构对应的代码，并补齐或运行测试命令，保证构建 (`npm run build` / `pytest`) 绿灯。
4. **日志记录 (Log)**：将改动登记进 `WORKFLOW.md`。
5. **循环 (Iterate)**：准备进入下一个方向的整理。

---

## 附录：可参考的系统架构与设计模式

AI 在产出 Spec 时，应从下表中主动判断是否有适合当前痛点的架构或模式，并在 Spec 中说明"选用 / 不选用"及原因。

### 系统架构（System Architecture）

| 架构 | 描述 | 本项目典型应用场景 |
|------|------|-----------------|
| 单体架构（Monolith） | 所有功能放一个部署单元 | 当前后端现状，重构目标是在内部分层而非拆服务 |
| 分层架构（Layered） | Controller → Service → DAO/Repository | **后端首选**：Router 仅做参数校验，Service 编排业务，DB 层隔离存储 |
| MVC | Model、View、Controller 分离 | FastAPI + Pydantic Schema 已体现此结构 |
| MVVM | Model、ViewModel、View（双向绑定） | **前端首选**：React Context/Store 充当 ViewModel，Pages 为 View |
| 前后端分离 | React 调后端 REST API | 当前架构现状，保持 |
| 微服务（Microservices） | 大系统拆成多个独立服务 | Agent Service 已是独立服务；后端暂不拆分 |
| 事件驱动（EDA） | 消息/事件解耦系统 | Agent → Backend Webhook 回调已是此模式的体现 |
| 管道-过滤器（Pipe & Filter） | 数据流经一系列处理阶段 | AI Pipeline、评分链路、SSE 流式输出 |
| BFF（Backend for Frontend） | 为特定前端定制的聚合后端 | 若未来出现多端（App/Web），可在 Backend 层增加 BFF 聚合 |
| 六边形架构（Hexagonal） | 核心业务与外部适配器（DB/API/LLM）隔离 | Agent Service 的理想形态：推理核心不依赖外部实现 |
| CQRS | 读写分离，命令与查询走不同路径 | 学习路径/评估等写少读多的模块可考虑 |
| Clean Architecture | 依赖规则：内层不依赖外层 | 与分层架构组合使用，防止 Router 层直接操作 DB |

### 设计模式（Design Patterns）

#### 创建型

| 模式 | 本项目应用场景 |
|------|--------------|
| 单例（Singleton） | DB 连接池、LLM Client 实例 |
| 工厂方法（Factory Method） | 根据课程类型创建不同评估策略 |
| 建造者（Builder） | 复杂 Prompt 模板的分步构造 |

#### 结构型

| 模式 | 本项目应用场景 |
|------|--------------|
| 适配器（Adapter） | Agent 返回结构 → 前端 DTO 转换层 |
| 外观（Facade） | Agent Service 对外暴露统一 HTTP 接口，隐藏内部推理细节 |
| 代理（Proxy） | Axios 实例封装（统一加 token、拦截 401） |
| 装饰器（Decorator） | FastAPI 依赖注入（`Depends`）、Python `@router.get` |

#### 行为型

| 模式 | 本项目应用场景 |
|------|--------------|
| 责任链（Chain of Responsibility） | **FastAPI Middleware 链**：认证 → 限流 → 日志 → 路由；前端 Axios 拦截器链 |
| 观察者（Observer） | SSE 流式推送、EventBus 跨组件通知 |
| 策略（Strategy） | 不同学科/难度的评分算法可互换；LLM 模型选择策略 |
| 模板方法（Template Method） | Agent 推理骨架固定，具体步骤（Prompt/工具调用）可重写 |
| 状态（State） | 学习路径节点状态机（未开始 → 进行中 → 已完成） |
| 命令（Command） | 用户操作封装为命令对象（支持撤销/重放） |
| 中介者（Mediator） | ChatContext 充当各组件间通信的中介，避免组件直接互相依赖 |

### 横切关注点与工程模式

| 分类 | 描述 | 本项目应用场景 |
|------|------|--------------|
| 过滤器/中间件 | 请求拦截链，处理认证/日志/限流 | FastAPI Middleware；前端 Axios 拦截器（**方向 2 网络层整理的核心手段**） |
| 仓储模式（Repository） | 数据访问抽象，业务层不感知存储细节 | 后端 Service 层不直接写 SQL，通过 Repository 接口操作 DB（**方向 1 分层的关键** ） |
| DTO / Schema 分离 | 传输对象与领域对象隔离 | Pydantic Schema 清洗 Agent 返回字段（**方向 5 数据清洗**） |
| 依赖注入（DI） | 控制反转，提升可测试性 | FastAPI `Depends()`；React Context |
| 幂等性设计 | 重复请求结果一致 | 学习进度提交、评估写入接口 |
| 缓存策略（Cache-Aside） | 先查缓存，缓存未命中再查 DB | 知识图谱节点、课程目录等高频读低频写数据 |
| API Gateway 模式 | 统一入口，路由/认证/限流 | 若 Agent Service 接口增多，可在 Backend 增加统一代理层 |
