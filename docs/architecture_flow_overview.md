# 系统架构与数据流设计总览 (Architecture & Flow Overview)

本文档提供了 EDUagent 项目中各核心模块的系统架构、内部工作流以及数据流的全面总览，方便开发人员快速理解系统运行脉络。

---

## 1. AI 对话与辅导模块 (AI Chat & Tutoring)

AI 对话与辅导模块通过服务器发送事件 (SSE) 建立了一个实时的交互式对话辅导助手。前端利用 SWR 进行会话历史列表与推荐资源的同步缓存，并利用 React 本地状态处理高频的流式消息块渲染。

### 1.1 业务流程图
```
[前端页面: AIChat.jsx]
      │  1. 发送消息 / 触发对话
      ▼
┌──────────────┐
│ ChatContext  ├───────────────────────────────────┐
└──────┬───────┘                                   ▼
       │  2. POST /api/v1/tutoring/chat     [useRecommendedResources]
       │                                           │ (SWR 缓存优先)
       ▼                                           ▼
┌──────────────┐                                 根据当前聊天中的
│  后端API路由 │                                 活跃知识点动态过滤推荐课件
└──────┬───────┘
       │  3. 通过 SSE 转发 Payload 调起智能体
       ▼
┌──────────────┐
│ 答疑智能体   │  4. 从 Qdrant 向量库检索学生专属记忆与课程切片
│(AgentService)│  5. 运行 ReAct 推理循环 (调用并执行相关工具)
└──────┬───────┘
       │  6. 按 SSE Chunk 格式向后端流式输出 (正文、Mermaid导图、推荐知识点、done事件)
       ▼
┌──────────────┐
│ 流式适配器   │ (后端代理 - 缓冲并规整分片，保证 UTF-8 编码完整并处理 done 持久化)
└──────┬───────┘
       │  7. 将规整的流式块数据推送给前端
       ▼
┌──────────────┐
│ ChatContext  │  8. 实时解析 SSE Chunk，拼接并更新前端本地 Message 数组状态
└──────┬───────┘  9. 监听到 'done' 事件后，利用 mutate(sessions) 乐观拉取历史会话列表
       │
       ▼
[展示视图] (前端渲染 Markdown / 编译 Mermaid 流程图 / 展示薄弱知识点 / 工具卡片)
```

### 1.2 MVVM 模块职责划分
- **Model (数据模型)**: 数据库实体 (`TutoringSession`, `Message`, `Resource`, `CourseKnowledgeGraph`)。
- **ViewModel (视图模型)**: 
  - [ChatContext.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/context/ChatContext.jsx) (管理对话上下文生命周期、SSE 握手与连接重试、SWR 列表缓存和删除等乐观 UI 更新)。
  - [useRecommendedResources.js](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/hooks/useRecommendedResources.js) (自定义 SWR Hook，拉取课程备选资源，并根据助理消息中提取的活跃知识点在前端进行实时过滤匹配)。
- **View (表现层视图)**: 
  - [AIChat.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/AIChat.jsx) 页面容器布局。
  - [SidebarHistory.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/chat/SidebarHistory.jsx) (会话历史树状侧边栏)。
  - [SidebarResources.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/chat/SidebarResources.jsx) (课例推荐展示侧边栏)。
  - [ChatArea.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/chat/ChatArea.jsx) (流式对话气泡展示与输入发送控制)。
  - [ChatMessage.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/chat/ChatMessage.jsx) (富文本 Markdown 解析、Mermaid 图表图形编译渲染器)。

---

## 2. 学情评估模块 (Evaluation)

学情评估模块提供结构化的学生表现评估追踪（包含知识点进度、章节掌握度以及资源使用分布）。该模块采用瘦路由 (Thin Router)、业务服务层 (Service Layer) 和后台异步任务执行器 (Background Task Worker) 的三层架构，实现逻辑解耦。

### 2.1 业务流程图
```
[用户客户端]
      │  1. 发起刷新评估请求: POST /api/v1/evaluation/refresh
      ▼
┌──────────────┐
│  后端API路由 │
└──────┬───────┘
       │  2. 实例化业务类并委派
       ▼
┌──────────────┐
│  学情评估    │  3. 校验用户有效选课权限: verify_course_enrollment()
│  Service 服务├─────────────────────────────────┐
└──────┬───────┘                                 ▼
       │                                  [CourseEnrollment]
       │  4. 检查是否有并发运行中的刷新任务: _get_processing_refresh_task()
       │  5. 组装输入数据上下文: _assemble_evaluation_payload()
       │  6. 在 DB 预先生成 status 为 'processing' 的异步任务: create_refresh_task()
       │  7. 提交当前 DB 短事务并确认落库
       │  8. 立刻响应 HTTP 202 Accepted 并带回任务 ID (task_id)
       │
       │  9. 调度 asyncio.create_task() 进入异步后台运行
       ▼
┌──────────────────────────────────────┐
│ run_evaluation_refresh_background()  │ (在新开辟的数据库会话上下文中执行)
└──────────────┬───────────────────────┘
               │  10. 调用 Agent 服务 POST /agent/v1/evaluation/generate (传递大量画像与活动上下文)
               ▼
        ┌──────────────┐
        │Agent Service │  (大模型进行多维学情矩阵数据推导，输出 JSON)
        └──────┬───────┘
               │  11. 返回结构化评测大纲 JSON 结果
               ▼
┌──────────────────────────────────────┐
│ run_evaluation_refresh_background()  │
└──────────────┬───────────────────────┘
               │  12. 获取命名锁: evaluation_lock() (防重入与脏写，兼容 MySQL/SQLite)
               │  13. 软删除历史评测报告: 将 is_deleted 置为 True
               │  14. 写入全新 Evaluation 记录 (写入 mastery_table 掌握度与 progress_table 进度表)
               │  15. 更新 AsyncTask 状态 (status = 'completed') 并填入完成时间
               │  16. 提交事务，安全释放数据库命名锁
               ▼
           [落库成功]
```

### 2.2 数据流核心组件
1. **输入载荷 (Request Payload)**: 仅包含 `course_id`。
2. **组装至 Agent 的上下文环境 (Context Payload)**:
   - `student_profile`: 学生的专业、年级和辅导脚手架配置级别。
   - `profile_context`: 模态偏好、知识坐标、认知盲区和学习意志意图。
   - `kg_context`: 活跃知识图谱节点和学生当前进度映射。
   - `learning_activity`: 交互活动总数、在线时长、活跃天数和时间戳。
   - `learning_progress`: 章节整体完成率。
   - `quiz_results`: 测验答题历史、正确率统计与知识点测验波动趋势。
   - `resource_usage`: 按类型（视频、代码、文档等）分类的点击查阅次数。
3. **Agent 输出格式**:
   - `progress_table`: 各章节和节点的进度表。
   - `mastery_table`: 知识点掌握水平分级列表。
   - `resource_usage_table`: 课例查阅指标。
   - `summary_text`: 由智能体生成并润色的学情总结文字。
4. **数据库状态更新**: `Evaluation` 表写入记录（`is_deleted=False`），`AsyncTask` 任务状态推进为 `completed`。

---

## 3. 资源入库与知识图谱生成模块

管理员控制台支持将原始的讲义/书籍材料上传，并利用 Agent 快速扫描分析以自动构建章节、知识点和连线，形成课程核心“知识图谱”，同时录入向量库以便 AI 进行检索。

### 3.1 资料入库流程
```
[管理员后台]
      │  1. 上传课程讲义/材料 (支持 PDF/TXT 等)
      ▼
┌──────────────┐
│  后端API路由 │  2. 在 MySQL 中创建 CourseCatalogMaterial 记录
└──────┬───────┘  3. 调用入库接口: POST /admin/course-catalogs/{id}/ingestions
       │  4. 开启异步线程派发入库任务
       ▼
┌──────────────────────────────────────┐
│  run_catalog_ingestion_background()  │
└──────────────┬───────────────────────┘
               │  5. 请求 Agent：POST /agent/v1/knowledge/ingest
               ▼
        ┌──────────────┐
        │Agent Service │  6. 进行文本清洗、章节检测并划分文本块 (Chunking)
        └──────┬───────┘  7. 对每个文本块进行 Embedding 向量特征提取
               │  8. 批量写入 Qdrant 向量集合 (以目录 ID 为分区和查询隔离标识)
               ▼
        [Qdrant DB] (已嵌入完毕的向量切片库，供 Tutoring SSE 对话执行 RAG 检索)
```

### 3.2 知识图谱 (KG) 生成流程
```
[管理员后台]
      │  1. 一键触发图谱建立: POST /admin/course-catalogs/{id}/knowledge-graphs/generations
      ▼
┌──────────────┐
│  后端API路由 │  2. 初始化异步任务 AsyncTask (status='processing')
└──────┬───────┘  3. 异步并发唤起大模型分析
       │
       ▼
┌──────────────────────────────────────┐
│ run_catalog_kg_generation_background │
└──────────────┬───────────────────────┘
               │  4. 请求 Agent：POST /agent/v1/knowledge/kg/generate
               ▼
        ┌──────────────┐
        │Agent Service │  5. 从 Qdrant 向量库中提取文档摘要和核心提纲
        └──────┬───────┘  6. 调用大模型提炼知识结构，返回章节 (chapters)、节点 (nodes) 与连线 (edges)
               │  7. 返回结构化关系格式 JSON 数据
               ▼
┌──────────────────────────────────────┐
│ run_catalog_kg_generation_background │
└──────────────┬───────────────────────┘
               │  8. 校验节点并映射对应数据约束
               │  9. 写入 CourseKnowledgeGraph 图谱数据表，标记为激活使用
               │  10. 设置 AsyncTask 状态为 'completed' 
               ▼
           [图谱激活落库]
```

---

## 4. 课程学习资源深度生成模块

在建立了图谱之后，该模块可通过多智能体协同工作流（Multi-Agent Orchestration）批量或单点生成涵盖四大方向的精细学习资源（知识讲解、思维导图、拓展阅读、代码示例），并通过 Webhook 异步回调落库。

### 4.1 业务流程图
```
[管理员 / 调度系统]
      │  1. 发起资源深度生成请求 (POST /api/v1/course-catalogs/{id}/resources/generations)
      ▼
┌──────────────┐
│  后端API路由 │  2. 创建 AsyncTask (状态=processing, 初始化进度=10%)
└──────┬───────┘  3. 调用 Agent：POST /agent/v1/resources/generate (将 task_id 与 webhook_url 传入)
       │  4. 接口直接响应 202 Accepted 状态，前端无阻碍继续操作
       ▼
┌──────────────┐
│Agent Service │  5. accept_resource_generation() 记录任务，返回任务估算耗时
└──────┬───────┘  6. 派发后台工作流：run_resource_generation_task()
       │
       ▼
┌──────────────────────────────────────┐
│  run_multi_agent_resource_workflow   │ (AgentScope 架构下的多 Agent 工作流)
└──────────────┬───────────────────────┘
               ├─► [Planner 智能规划器] ──► 生成资源规划纲要 ResourcePlan (LLM / 规则兜底)
               ├─► [Parallel Resource Agents 任务智能体分发] (根据 Qdrant RAG 召回内容各自作业)
               │     ├── DocumentAgent  ──► 提炼生成深度知识讲解 (Markdown 格式文本)
               │     ├── MindmapAgent   ──► 输出逻辑思维导图 (Mermaid.js 图表图定义)
               │     ├── ReadingAgent   ──► 扩展并检索参考阅读、关联案例文献
               │     └── CodeAgent      ──► 编写匹配该知识节点的经典练习代码与注释
               ├─► [Resource Critic 审核智能体] ──► 校验大模型语法、格式和内容合规性
               └─► [Aggregator 结果集成器] ──► 组装生成完整的资源大对象
                       │
                       ▼ 7. 发送 HTTP POST 回调通知后端: /api/v1/webhooks/agent
┌──────────────┐
│Webhooks API  │  8. verify_webhook_secret() 对头部进行解密安全验证
└──────┬───────┘  9. 解析并校验资源的 fields (包含 type, title, content, kp 映射)
       │  10. 在事务中批量循环向 Resource 资源表写入数据
       │  11. 将对应的 AsyncTask 状态更改为 'completed' (完成进度更新为 100%)
       ▼
    [MySQL DB]
```

---

## 5. 核心学习与个性化学习路径模块

学生端在进入课程学习后，由系统根据画像和学情数据自动生成一条定制的学习路径。每个节点的学习状态会根据最新的测评数据进行更新和引导。

### 5.1 业务流程图
```
[学生前端页面]
      ├─► GET /api/v1/learning-path (拉取当前激活的节点和连线序列)
      │
      └─► POST /api/v1/learning-path/refresh (根据最近活动重新规划学习路径推荐)
            │
            ▼
      ┌──────────────┐
      │  后端API路由 │  1. 校验学生的 CourseEnrollment 选课有效性
      └──────┬───────┘  2. assemble_payload(): 收集最新学情 Evaluation 以及用户画像 UserProfile
             │  3. 写入 AsyncTask (processing) 并提交事务
             │  4. 触发后台刷新进程: run_learning_path_refresh_background()
             ▼
      ┌──────────────────────────────────────┐
      │ run_learning_path_refresh_background │
      └──────────────┬───────────────────────┘
                     │  5. 发送 Agent 请求: POST /agent/v1/learning-path/generate
                     ▼
              ┌──────────────┐
              │Agent Service │  6. 大模型分析薄弱点坐标和先修课要求，输出规划
              └──────┬───────┘  7. 规则兜底引擎: 将画像中存在 blindspots 的节点设为推荐
                     │  8. 返回处理后的节点状态、掌握分数和详细的推荐理由
                     ▼
      ┌──────────────────────────────────────┐
      │ run_learning_path_refresh_background │
      └──────────────┬───────────────────────┘
                     │  9. 锁定命名锁: learningpath_{user_id}_{course_id}，防止并发脏写
                     │  10. 将该用户本门课程的原路径全部标记为 is_deleted = True 逻辑删除
                     │  11. 批量持久化全新 LearningPath 并更新对应的 AsyncTask 状态为已完成
                     │  12. 释放命名锁，提交整个数据保存事务
                     ▼
                 [落库成功]
```

### 5.2 知识节点状态定义 (Pathway Status)
- **recommended (推荐学)**: 当前最适合攻克的核心弱项或必须先行掌握的基础前置节点。
- **in_progress (学习中)**: 已经查阅过关联课件/做了部分练习但尚未通过掌握度测试的节点。
- **completed (已掌握)**: 在该节点的随堂测验中综合得分达到设定阈值（通常为 >= 80%）的知识节点。
- **pending (待学习)**: 尚未接触或尚未解锁前置关联技能的其余非推荐节点。

---

## 6. 个性化测试与 AI 诊断模块

测试模块支持从保底测试库读取题目或请求智能体即时出题，并在学生完成作答后，异步唤起大模型对做答详情进行全面剖析以给出定性反馈。

### 6.1 测试生命周期与诊断生成流程
```
[学生测试页面]
      ├─► GET /api/v1/quiz/questions (拉取测验题目，自动在后端创建 QuizSession 以追踪生命周期)
      │
      └─► POST /api/v1/quiz/generate (请求生成专门针对该薄弱点的定制个性化测验)
            │
            ▼
      ┌──────────────┐
      │  后端API路由 │  1. 开启异步任务 AsyncTask (processing)
      └──────┬───────┘  2. 调用 Agent 接口: POST /agent/v1/assessment/generate-questions
             │  3. Agent 动态组卷并返回出题数据
             │  4. 后端解析并将题目写入 QuizQuestion (source="personalized", owner=该学生)
             │  5. 标记出题 AsyncTask 状态为已完成，接口返回 HTTP 202 Accepted 
             ▼
[提交测验答案]
      │  1. 学生答题完成，发起提交: POST /api/v1/quiz/submit
      ▼
┌──────────────┐
│  后端API路由 │  2. 在 QuizAnswer 中完整持久化每道题的选择和耗时
└──────┬───────┘  3. 与答案自动对比计分, 更新 QuizSession 的客观分数与提交时间
       │  4. 启动后台异步任务 asyncio.create_task(run_diagnosis_background) 并向前端响应
       ▼
┌─────────────────────────────┐
│  run_diagnosis_background   │
└──────────────┬──────────────┘
               │  5. 调用 Agent 服务评价接口: POST /agent/v1/assessment/evaluate (携带问题与回答)
               ▼
        ┌──────────────┐
        │Agent Service │  6. 大模型综合判卷，诊断概念认知偏差和解题错误原因
        └──────┬───────┘  7. 返回结构化定性诊断总结文本
               ▼
┌─────────────────────────────┐
│  run_diagnosis_background   │
└──────────────┬──────────────┘
               │  8. 写入 QuizSession.diagnosis 字段
               │  9. AsyncTask 置为 'completed'
               ▼
           [诊断入库完成]
```

---

## 7. 学生画像刷新与动态引导模块

学生画像包括了对感官学习偏好（模态）、教学主动性（引导层级）以及动态认知掌握度雷达图的数据记录。画像的更新流程旨在根据学生的真实互动，自动化、实时地计算这些高维特征。

### 7.1 学生画像刷新流程
```
[画像刷新触发 (页面访问或自动轮询)]
      │  1. 请求刷新画像: POST /api/v1/profile/refresh
      ▼
┌──────────────┐
│  后端API路由 │  2. 创建画像更新 AsyncTask (status='processing') 记录
└──────┬───────┘  3. 异步派发后台进程: run_profile_refresh_background()
       │  4. 响应前端 202 成功开始受理
       ▼
┌──────────────────────────────────────┐
│    run_profile_refresh_background    │
└──────────────┬───────────────────────┘
               │  5. 获取画像写命名锁: profile_lock(user_id, course_id) 防止更新重叠
               │  6. 聚合拉取该学生所有的做题错误、学习时长统计、课件点击模态分布
               │  7. 运行内置规则策略 compute_profile_fields():
               │     - 模态偏好 (Modal Preference): 统计各媒介形式阅读交互重新加权。
               │     - 引导层级 (Guidance Level): 匹配系统启发式支架规则 (L1, L2, L3)。
               │     - 认知盲区与弱项: 聚合测验和聊天中的高频负反馈知识点。
               │  8. 用 flag_modified 机制安全更新 UserProfile 对应字段并刷入 MySQL
               │  9. 完成 AsyncTask 状态变更，最终释放锁资源
               ▼
           [画像更新完成]
```

---

## 8. 系统物理与逻辑边界

项目通过严格的分层，划定了表现层前端、业务控制网关后端和智能体逻辑服务三者的边界：

```
┌────────────────────────────────────────────────────────────┐
│                       React 前端                           │
│  SWR 状态同步 / ViewModels 视图模型 / 全局 Context 共享    │
└─────────────┬────────────────────────────────┬─────────────┘
              │ HTTP Client API 请求           │ HTTP Client API 请求
              ▼                                ▼
┌──────────────────────────────┐       ┌─────────────────────┐
│       FastAPI 后端           │◄─────►│    智能体服务       │
│ 数据库事务隔离 / 短事务生命周期│ HTTP  │ 知识库检索 RAG / LLM│
│ MySQL 主数据库 / AsyncTask   │ 内部  │ 异步Webhook / Qdrant │
└──────────────────────────────┘  API  └─────────────────────┘
```

### 架构规约与防御原则
1. **禁止直连数据库 (Database Access Constraint)**: `Agent Service` 在任何场景下都**绝对禁止**引入直连后端 MySQL 数据库的代码和配置。所有的状态维护和最终持久化行为均属于后端的专有职责。
2. **异步握手协议模式 (Asynchronous Handshake Pattern)**: 所有与智能体进行的大算力、长耗时作业交互，均必须通过 `202 Accepted + AsyncTask 唯一任务 ID` 的模式解耦。Agent 在完成后以 POST 形式向后端的 `/api/v1/webhooks/agent` 发起 Webhook 回调，由后端写入资源数据。
3. **数据竞态与命名锁防护 (Named Locks Isolation)**: 为防止并发环境或网络重复发起点击导致画像、学习路径和评估报告等核心实体记录产生数据覆盖或乱序，所有关键后台更新必须使用 `GET_LOCK(lock_name, timeout)` 以确保串行执行和并发安全。
