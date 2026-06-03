# EduAgent — 个性化学习多智能体系统

> **软件杯 A3 赛题** | 基于大模型的个性化资源生成与学习多智能体系统开发

一个采用微服务架构的智能教育系统，通过多智能体协作为学生提供个性化学习资源生成、学习路径规划与智能辅导。

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     👤 用户 (浏览器)                         │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  🌐 Web Backend (Port 8001)                                 │
│  职责: 鉴权 · 静态托管 · 对话持久化 · 代理转发               │
│  负责人: 同学B                                               │
└──────────────────────────┬──────────────────────────────────┘
                           │  HTTP API (/agent/*)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  🧠 Agent Service (Port 8002)                               │
│  职责: 智能辅导 · 记忆压缩 · 测验评估 · 资源生成 · RAG检索   │
│  负责人: 同学A                                               │
└─────────┬───────────────┬───────────────┬───────────────────┘
          │               │               │
          ▼               ▼               ▼
      向量数据库       大模型 API       课程知识库
      (Qdrant)       (讯飞)    (dataset/)
```

**核心原则：Agent 不碰 SQL（但直接读写 Qdrant 向量库），Backend 不碰大模型。两个服务通过 HTTP API 解耦。**

---

## 二、模块划分与职责

项目分为以下四个模块，各模块职责明确，实际目录结构由开发者自行组织。

### 🧠 Agent Service（同学A）

半无状态的 AI 计算服务。自身拥有 Qdrant 向量库（课程知识 + 用户记忆），不碰 SQL。

> **路由方式**：后端通过不同 URL 路径分发请求（无 Router Agent），零出错、零额外延迟。

| 入口接口 | 工作流模式 | 智能体/工具 |
|--------|--------|--------|
| `POST /agent/v1/tutoring/chat` | 单体 Agent + Tool Calling | 辅导 Agent（含 search_knowledge / draw_diagram / run_code），自行查 Qdrant |
| `POST /agent/v1/profile/initialize` | 单体 Agent 引导对话 | 冷启动画像 Agent |
| `POST /agent/v1/assessment/evaluate` | Pipeline 状态机 | 对比答案 - 提取盲区 - 更新掌握度 - 推荐下一步 |
| `POST /agent/v1/resources/generate` | Manager-Worker 并行 | Manager + 5 个 Worker（讲解/导图/习题/拓展/代码），Webhook 回调 |
| `POST /agent/v1/memory/compress` | Pipeline 状态机 | 摘要压缩 + 事实提取存 Qdrant |

| 基础设施 | 职责 |
|--------|------|
| **工具层** | 知识检索（向量 + BM25 混合）、代码沙箱、内容安全过滤 |
| **记忆管理** | 上下文组装 + Qdrant RAG 检索（Agent 自行查询，不依赖 Backend 预检索） |
| **Prompt 管理** | 各智能体的 Prompt 模板集中管理，不硬编码在代码中 |

### 🌐 Backend（同学B）

薄网关层，管用户、管数据、管转发。自身不包含任何 AI 逻辑。

| 子模块 | 职责 |
|--------|------|
| **API 路由** | 对话、画像、历史记录、资源列表、学习路径等接口 |
| **业务逻辑** | 对话存取 + 摘要触发、画像持久化、生成资源管理、与 Agent Service 的通信封装 |
| **数据库** | ORM 模型（对话历史、用户画像、资源记录等） |
| **中间件** | 简单鉴权（JWT 或 Session） |

### 💻 Frontend（同学B）

用户界面，重点关注流式渲染和多模态内容展示。

| 页面 | 功能 |
|------|------|
| 对话界面 | 流式输出 + Markdown 渲染 + 代码高亮 |
| 画像看板 | 学生画像雷达图/可视化展示 |
| 学习路径 | 路径时间线/路线图展示 |
| 资源浏览 | 多模态资源卡片化展示与下载 |
| 在线答题 | 测验界面 |

### 🗂️ Dataset（同学A）

课程知识库原始资料及入库处理脚本。选取一门完整的高校专业课程作为切入点。

---

## 三、目录结构参考

> ⚠️ **以下仅为参考示例。** 实际目录由各负责人根据开发需要自行调整，但需保持模块间的隔离边界。

```
EduAgent/
├── agent_service/              # 🧠 Agent 核心服务 [同学A]
│   ├── main.py                 #   服务入口 (port 8002)
│   ├── agents/                 #   智能体定义
│   ├── sub_agents/             #   资源生成子智能体
│   ├── tools/                  #   工具（检索、时间解析、过滤等）
│   ├── memory/                 #   上下文组装、摘要
│   ├── prompts/                #   Prompt 模板
│   └── models/                 #   数据模型 / Pydantic Schema
│
├── backend/                    # 🌐 Web 后端网关 [同学B]
│   ├── main.py                 #   服务入口 (port 8001)
│   ├── api/                    #   路由定义
│   ├── services/               #   业务逻辑 + Agent 通信
│   ├── db/                     #   数据库 ORM + 迁移
│   └── middleware/             #   鉴权等中间件
│
├── frontend/                   # 💻 Web 前端 [同学B]
│   └── src/
│       ├── views/              #   页面
│       ├── components/         #   通用组件
│       └── api/                #   接口封装
│
├── dataset/                    # 🗂️ 课程知识库 [同学A]
│   ├── raw/                    #   原始文档
│   ├── processed/              #   清洗切片后的数据
│   └── scripts/                #   入库 & 校验脚本
│
├── tests/                      # 🧪 测试
├── docs/                       # 📖 比赛交付文档
└── deliverables/               # 🎬 PPT + 演示视频
```

---

## 四、接口契约

两个服务之间通过以下 HTTP API 通信。**修改接口时必须双方同步确认。**

> **完整的请求体/响应体格式见 `API_前端接口规范.md` 和 `API_Agent内部接口规范.md`。**

### 六维画像字段定义与计算方式

| 维度 | 字段名 | 类型 | 计算方式 | 谁来算 |
|------|--------|------|----------|--------|
| 模态偏好 | `modality_preference` | `{video,chart,text,code,formula}` 整数百分比 | 统计用户使用各类型资源的次数比例 | 后端 SQL COUNT |
| 引导粒度 | `guidance_level` | `"L1"/"L2"/"L3"` | 默认 L2，用户可手动调，LLM 可建议调整 | 用户手动 + Agent 建议 |
| 知识坐标 | `knowledge_coordinates` | `{mastered:[], learning:[]}` | mastery >= 0.7 归 mastered；当前路径节点归 learning | Agent 评估测验后返回 |
| 认知盲区 | `cognitive_blind_spots` | `string[]` | LLM 从对话/测验错题中提取反复犯错的知识点 | Agent LLM 提取 |
| 驱动意图 | `drive_intent` | `"daily"/"exam_cram"` | 近 7 天学习频率：高频=exam_cram，低频=daily | 后端 SQL 统计 |
| 学科底座 | `discipline_base` | `"bronze"/"silver"/"gold"` | AVG(所有知识点 mastery)：<0.3=bronze, 0.3~0.7=silver, >0.7=gold | 后端 SQL AVG |

> **黄金法则：LLM 只输出枚举值和文本列表，代码负责所有数值计算。**

### Agent Service 暴露的接口（Backend -> Agent）

> 完整的请求体/响应体见 [`API_Agent内部接口规范.md`](./API_Agent内部接口规范.md) 和 [`Agent-Service.openapi.json`](../Agent-Service.openapi.json)

| 接口 | 方法 | 用途 | 返回方式 |
|------|------|------|----------|
| `/agent/v1/tutoring/chat` | POST | 智能辅导对话（Agent 自行查 Qdrant） | SSE 流式 |
| `/agent/v1/profile/initialize` | POST | 冷启动画像引导对话 | SSE 流式 |
| `/agent/v1/profile/generate` | POST | 生成/刷新用户画像 | 同步 JSON |
| `/agent/v1/evaluation/generate` | POST | 生成学习效果评估 | 同步 JSON |
| `/agent/v1/assessment/evaluate` | POST | 测验评估与诊断 | 同步 JSON |
| `/agent/v1/learning-path/generate` | POST | 生成个性化学习路径 | 同步 JSON |
| `/agent/v1/resources/generate` | POST | 异步多类型资源生成 | 202 + Webhook 回调 |
| `/agent/v1/memory/compress` | POST | 记忆压缩与事实提取 | 同步 JSON |
| `/agent/v1/health` | GET | 健康检查 | 同步 JSON |

### SSE 事件统一格式

```
event: message
data: {"type": "<event_type>", "content": "<content>"}\n\n

event: done
data: {"status": "finished"}\n\n
```

| type | 含义 | 示例 |
|------|------|------|
| `chunk` | 文本内容片段 | 逐字/逐块输出 |
| `diagram` | 图解数据 | Mermaid 语法或图表 JSON |
| `knowledge_points` | 引用的知识点 | `[{"name":"二叉树","chapter":"第3章","mastery":60}]` |
| `suggestion` | 学习建议 + 推送例题 | `{"text":"建议复习...","exercises":[...]}` |
| `done` | 本轮对话完成 | `{"conversation_id":"...","message_id":"..."}` |

---

### 五、数据流与记忆策略

#### 1. 对话记忆 (基于滑动窗口与双轨记忆机制)

为了在控制 Token 消耗的同时实现“无限上下文”与“深度个性化”，系统采用长短期记忆分离的流转策略：

- **全量持久化**：关系型数据库（SQLite/MySQL）全量保存所有原始对话历史，仅用于前端展示和数据溯源。
- **动态上下文窗口**：传给 Agent 的 Prompt 结构严格控制长度，格式为：
  `[系统设定] + [全局历史摘要] + [用户画像] + [长期记忆检索结果] + [最近 N 轮对话(缓冲区)] + [当前消息]`
- **触发压缩与提炼 (滑动窗口机制)**：
  设定阈值（如每满 20 轮对话触发一次后台异步任务）：
  1. **更新全局摘要**：调用轻量级 LLM，将 `[旧全局摘要] + [最早的 10 轮对话]` 融合成新的 `[全局历史摘要]`。
  2. **提取语义记忆 (Fact Extraction)**：调用 LLM 从这 10 轮对话中提取用户的“学习盲点”、“已掌握知识点”和“认知偏好”，作为独立条目存入**用户向量数据库 (User Memory)**。
  3. **滑动清理**：从当前活跃上下文中移除这最早的 10 轮原始对话，仅保留最近的 10 轮以维持对话的自然连贯性。
- **记忆召回 (RAG for Memory)**：每次用户输入新消息时，将其向量化并在“用户向量数据库”中检索。将检索到的历史事实（如：“用户之前在递归概念上卡壳过”）作为 `[长期记忆检索结果]` 注入当前 Prompt，实现跨轮次的“防遗忘”辅导。

#### 2. 知识检索 (防幻觉 RAG 增强架构)

针对专业课程和代码类实操案例的生成，系统采用增强型 RAG（检索增强生成）管线，从根源上降低大模型幻觉：

- **Query 重写 (Query Rewrite)**：用户的当前提问往往包含指代词（如“这个怎么用”）。在检索前，利用轻量级 LLM 结合最近几轮对话，将用户输入重写为独立、完整的搜索词（Standalone Query）。
- **混合检索 (Hybrid Search)**：
  - **向量检索 (Dense Retrieval)**：基于语义相似度查找概念和原理。
  - **关键词检索 (Sparse/BM25)**：针对代码片段、特定变量名、专有名词进行精准匹配，弥补纯向量检索在代码场景下的召回缺陷。
- **精准重排 (Reranking)**：混合检索召回 Top 30 的文档切片后，接入 Cross-Encoder 重排模型（如 bge-reranker）进行二次语义打分。仅取打分最高的 Top 5 切片喂给 LLM，剔除低相关性噪音。
- **时间感知与元数据过滤**：入库时提取时间锚点、章节、难度等存入元数据。对话中，仅当 Query 包含明确的时效性意图（如“最新的考试大纲”）或特定范围时，才将元数据作为硬过滤条件，平时作为次要排序权重。

#### 3. 轻量级逻辑图谱 (Graph-RAG Lite)

为实现精准的“个性化学习路径规划”与“画像看板”，系统引入轻量级图谱架构，避免重型图数据库的维护成本与查询幻觉：

- **底层拓扑 (静态 JSON)**：通过结构化 JSON 定义专业课程知识点之间的严格前置依赖关系（如：递归 -> 二叉树遍历 -> DFS），作为路径规划的绝对逻辑基准。
- **中间层融合 (Metadata 注入)**：将图谱节点 ID 和依赖关系作为 Metadata 注入向量数据库的文档切片中。检索时不仅召回当前知识点，同时召回其“前置/后置”知识上下文。
- **表现层渲染 (动态星空图)**：在用户画像中维护各知识点节点的掌握度（0~1）。前端利用 ECharts/AntV G6 将其渲染为动态知识网络图，直观展示用户的能力边界与薄弱环节。

#### 4. 画像更新时机

不要每轮更新，按以下触发规则：

| 触发条件 | 更新哪些维度 | 谁来算 |
|----------|------------|--------|
| 提交测验 | 知识坐标、认知盲区、学科底座 | Agent 评估后返回，后端存 SQL |
| 每 10 轮记忆压缩 | 认知盲区（从对话中补充提取） | Agent 提取 facts 存 Qdrant |
| 用户使用资源 | 模态偏好 | 后端 SQL 统计 |
| 每次登录 | 驱动意图 | 后端算近 7 天频率 |
| 用户手动调节 | 引导粒度 | 前端直接改，后端存 SQL |

---


## 六、技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| Agent 框架 | AgentScope | 多智能体协作 |
| 大模型 | 讯飞星火  | 赛题要求使用讯飞工具 |
| 向量数据库 | Qdrant（本地模式） | 知识检索，支持 metadata filter |
| 关系型数据库 | SQLite | 对话历史、用户画像、资源记录 |
| 后端框架 | FastAPI | 异步 + SSE 原生支持 |
| 前端框架 | Vue 3 + Vite（建议） | 也可纯 HTML |
| Markdown 渲染 | markdown-it + highlight.js | 代码高亮 |
| 思维导图 | Mermaid.js / ECharts | Agent 输出结构化数据，前端渲染 |

---

## 七、协作规范

### 分工边界

- **同学A** 只在 `agent_service/` 和 `dataset/` 中开发
- **同学B** 只在 `backend/` 和 `frontend/` 中开发
- 接口变更必须双方确认后再改

### Git 分支策略

```
main              ← 稳定可运行版本，不直接提交
├── dev           ← 日常集成分支，双方合并到这里
├── feat/agent-*  ← 同学A 的功能分支（如 feat/agent-router）
└── feat/web-*    ← 同学B 的功能分支（如 feat/web-chat-ui）
```

### Commit 规范

```
feat(agent): 完成路由智能体意图分类
feat(backend): 对话历史分页查询接口
feat(frontend): 流式对话气泡组件
fix(agent): 修复时间解析器时区问题
docs: 更新系统设计说明书
chore: 杂项
```

---

## 八、比赛交付物清单

| 交付物 | 要求 | 占分 |
|--------|------|------|
| 可运行的源码 + 数据集 | 文件整理规范，常规环境下可运行 | — |
| 演示 PPT | 应用价值、技术方案、创新点、核心功能 | 10% |
| 演示视频 | ≤ 7 分钟，展示操作流程与核心功能 | — |
| 配套文档 | 需求分析、系统设计开发、测试说明 | 10% |
| AI 工具说明 | 使用了哪些 AI Coding 工具 | — |
| 开源组件声明 | 标注名称、来源、协议 | — |
