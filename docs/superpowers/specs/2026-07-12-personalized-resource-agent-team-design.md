# 个性化资源 Agent Team 与公共资源语义重构设计

## 1. 背景与目标

EDUagent 当前存在三条相互割裂的学习资料生成链路：

- 管理员公共资源生成根据课程知识图谱批量生成共享资料；
- 个性化资源页面通过固定表单生成题目或复用公共资源接口；
- AI Chat 通过 AgentScope 2.x Agent、课程 RAG、学情工具、Workspace artifact 和代码题工具生成更丰富的内容。

赛题要求系统通过与学生智能交互，结合专业、课程内容、知识短板和学习需求，由不同角色智能体协作生成至少五种个性化、多模态学习资源。当前实现尚不能完整证明这一能力：AI Chat 的普通 artifact 没有统一沉淀到个性化资源库；手动个性化资料多数只具备私人归属而缺少充分的学情输入；公共资源类型存在名实不符；`leader_team.py` 使用普通 Python 类顺序调用模型，不是 AgentScope 官方 Agent Team。

本设计的目标是：

1. 明确公共资源与个性化资源的产品边界；
2. 让 `/learning-effects`、AI Chat 和个性化资源生成共享权威学情快照；
3. 使用 AgentScope 2.0.3 官方 Agent Team 实现三个有真实会话、状态和权限边界的角色；
4. 支持至少五类正式入库的个性化资源；
5. 将确定性验证与 Agent 审核分离，避免生成者自证和审核过严；
6. 保持 EDU HTTP/SSE 协议与 AgentScope 内部对象解耦。

## 2. 已确认的范围

### 2.1 本期包含

- 修订管理员公共资源类型语义；
- 公共资源覆盖全部有效 KG 节点；
- 修复学情统计中的事实语义问题；
- 建立可复用的 Evaluation 学情快照；
- 将个性化资源页面改造成统一的个人资料中心；
- 将 AI Chat 可保存 artifact 正式写入个性化资源体系；
- 将手动生成入口升级为自然语言需求驱动的智能生成入口；
- 使用一个 Leader 和两个 Worker 组成官方 Agent Team；
- 支持讲解文档、知识图、针对性练习、拓展阅读和代码实操五类个性化资源；
- 为工具建立角色专属白名单与一致性测试；
- 为正式资源建立确定性验证、宽松审核和 Backend 发布门槛。

### 2.2 本期不包含

- 视频或动画生成；
- 后台自动根据薄弱点批量生成资料；
- 管理员公共资源的草稿、人工审核和发布状态系统；
- 为每一种资源创建一个独立 Agent；
- 让 Agent 直接写 MySQL；
- 让 Backend 导入 Agent Service Python 模块；
- 让前端直接连接 Agent Service；
- 兼容或扩展 `/agent/v1/...` 协议；
- 将 AgentScope 原生事件直接暴露给 Backend 或 Frontend。

视频/动画作为后续第六类能力单独设计。学生薄弱点只在 `/learning-effects` 或 AI Chat 中形成生成建议，首期必须由学生确认后触发。

## 3. 当前实现审计结论

### 3.1 公共资源

管理员公共资源已经具备以下自动化链路：

```text
课程资料入库
  -> Active KG
  -> 为目标 KG 节点创建子任务
  -> Agent Service v2 生成
  -> Webhook 回传
  -> Backend 写入公共资源
  -> Catalog 绑定的教学班共享
```

但当前存在以下问题：

- `document` 实际生成 HTML 幻灯片，而不是普通文档；
- `code` 没有独立生成分支，会落入阅读材料兜底；
- `mindmap` 把内容用途和 Mermaid 表现形式混为一个顶层类型；
- 公共资料当前设置 `KG_RESOURCE_TARGET_LIMIT = 10`，与“全部有效 KG 节点”目标不一致；
- 现有 `CriticAgent` 只检查少数字段，却使用了编译审核语义。

公共题库已经遍历全部 KG 节点。公共资料也应改为遍历全部有效节点，而不是选择最多十个核心节点。

### 3.2 个性化资源页面

当前页面已经具备列表、任务状态、删除、题目分组和私密代码题入口，可继续作为业务权威页面。问题集中在生成入口：

- 学生只能选择章节、知识点和固定资源类型；
- 普通资料生成复用公共资源生成接口；
- 生成请求没有完整表达专业、困难、目标和学习偏好；
- `manual` 资源通常只是归属私人，内容未必充分个性化；
- 当前 `source_type` 只正式支持 `manual` 和 `quiz_wrong_answer`，AI Chat 普通 artifact 尚未统一入库。

### 3.3 AI Chat

AI Chat 当前使用 AgentScope 2.0.3 `Agent`、Toolkit、ToolGroup、PermissionContext、Workspace、Middleware 和 `reply_stream` 事件链，属于基本真实的 AgentScope 单 Agent 工作台。

它能够生成 Markdown、Mermaid 和代码题 artifact，也能读取学习进度、近期答题和课程 RAG。主要缺口是普通 artifact 仍以 Workspace 运行期文件为主，没有统一转为 Backend 权威个性化资源记录。

### 3.4 学习效果

`/learning-effects` 当前由 Backend 聚合事实、Agent Service 规则计算表格并调用一次模型改写 `summary_text`。它不是 AgentScope Agent。

当前事实聚合至少存在三项必须优先修复的问题：

1. 章节完成率和章节学习时长被初始化为固定的零；
2. “资源使用”统计的是课程资源数量，而不是学生实际使用行为；
3. 标注为最近十次的趋势可能读取了最早十次记录。

在这些事实语义修复前，Evaluation 不得作为个性化资源规划的可信依据。

### 3.5 当前所谓 Leader Team

`agent_service_v2/agents/leader_team.py` 使用普通 Python 类和手写循环调用模型及 Critic，不具备官方 Agent Team 的独立会话、消息总线、团队工具或 Worker 事件流，审计判定为 pseudo-framework。它只能作为待迁移业务原型，不能作为最终多智能体实现或比赛证明。

## 4. 产品边界

### 4.1 管理员公共资源

公共资源是基于课程资料和 KG 生成的标准教学底座，供绑定同一 Catalog 的教学班共同使用，不读取学生画像、错题或个体需求。

本期公共资源收敛为三类：

| 类型 | 内容 | 输出格式 |
|---|---|---|
| `lesson` | 标准知识讲义、概念、易错点和标准示例 | Markdown |
| `diagram` | 根据知识特征选择流程图、时序图、思维导图、结构图或状态图 | Mermaid |
| `example` | 讲解型完整代码、运行结果、错误与正确写法对比 | Markdown + 代码块 |

公共练习题继续归公共题库，不作为普通 `Resource` 中的代码题。

公共资源生成必须遍历全部有效 KG 节点。“有效”仅表示：

- 具有合法 `node_id`、名称和章节；
- 去重后唯一；
- 课程资料能够提供最低限度的检索依据。

不得再设置十个节点的业务上限。节点无效或没有课程依据时应记录明确失败原因，而不是生成无依据内容。

### 4.2 学生个性化资源

个性化资源结合课程依据与个人事实，只属于当前学生。统一支持以下五类：

| 类型 | 说明 | 主要呈现 |
|---|---|---|
| `personal_lesson` | 按专业、认知水平和薄弱点重新组织的讲解 | Markdown |
| `personal_diagram` | 针对当前理解困难选择合适图形 | Mermaid |
| `personal_practice` | 单选、多选、判断、简答、代码阅读或填空等针对性练习 | 结构化题目 |
| `personal_reading` | 结合专业方向、目标和课程 RAG 的拓展阅读 | Markdown + 来源 |
| `personal_code_problem` | 有参考解、公开/隐藏固定用例并可在 OJ 判题的实操任务 | CodeSandboxCard + Backend 题目实体 |

五类是系统能力集合，不要求每次请求全部生成。Leader 根据学生需求和学情证据选择必要组合。

### 4.3 统一入口和来源

个性化资源中心统一接收：

- `ai_chat`：AI Chat 对话生成并保存；
- `manual`：个性化资源页主动提出需求；
- `quiz_wrong_answer`：练习结果页由学生确认生成强化练习。

当前不存在自动薄弱点资料生成。首期不新增后台自动生成，仅允许 `/learning-effects` 提供带自然语言提示的“根据当前薄弱点生成资料”入口，学生确认后进入正常 Agent Team 流程。

## 5. 学情快照

### 5.1 事实与解释分离

Backend 是学习事实的权威来源，负责计算：

- KG 节点进度和掌握状态；
- 学习时长和活跃行为；
- 答题次数、正确率和真实近期趋势；
- 学生实际查看或使用的资源类型；
- Evaluation 快照版本和生成时间。

Agent 不得修改这些事实。

学情规划 Leader 负责：

- 将事实解释为学生可理解的总结；
- 识别有明确证据的优势和薄弱点；
- 给出优先级和下一步建议；
- 在收到资源需求时形成资源计划。

### 5.2 建议的结构化快照

```json
{
  "summary": "面向 /learning-effects 的 Markdown 总结",
  "strengths": [
    {
      "knowledge_point": "循环结构",
      "evidence": "最近 12 题正确率 91.7%"
    }
  ],
  "weak_points": [
    {
      "knowledge_point": "指针传参",
      "evidence": "最近 8 题正确率 37.5%",
      "priority": "high"
    }
  ],
  "learning_preferences": [],
  "next_actions": [],
  "facts_version": "opaque-version",
  "generated_at": "ISO-8601 timestamp"
}
```

`resource_plan` 不作为长期学情事实保存。它由 Leader 在具体生成请求中结合学情快照和本次自然语言需求动态产生，避免把一次性需求污染长期 Evaluation。

### 5.3 复用与失效

AI Chat 和个性化资源生成优先读取最近一次有效 Evaluation 快照。出现以下情况之一时才重新分析：

- Backend 学习事实版本发生变化；
- 快照不存在；
- 快照超过明确配置的有效期；
- 用户主动点击重新评估。

有效期必须由配置或产品规则确定，不能由 Agent 自行猜测。即使快照过期，旧快照仍可用于页面展示，同时标记待刷新，避免页面空白。

## 6. AgentScope 2.0.3 官方 Agent Team

### 6.1 采用官方托管模型

目标实现使用 `agentscope.app.create_app` 提供的 Agent Service 托管能力。官方 Team 的 Leader 和 Worker 是独立 Session，拥有独立状态、工作区绑定和事件流，通过消息总线及以下内置工具协调：

- `TeamCreate`
- `AgentCreate`
- `TeamSay`
- `TeamDelete`

不得通过自定义 `for` 循环和普通 Python Agent 类模拟团队。

本地 AgentScope 2.0.3 的实施事实为：

- `agentscope.app.create_app` 可用；
- `agentscope.app.SubAgentTemplate` 可用；
- `create_app` 的本地参数名为 `custom_subagent_templates`；
- 本地包没有 `agentscope.team` 或 `agentscope.service` 顶层模块。

文档示例与本地签名冲突时，以本地 2.0.3 包为准。任何尚未验证的 API 参数必须先通过 introspection 或最小测试确认。

### 6.2 角色

#### Leader：学情规划 Agent

Leader 是用户面对的会话，负责：

- 理解自然语言目标；
- 读取或刷新学情快照；
- 必要时读取近期答题和课程 RAG；
- 决定是否需要组建 Team；
- 形成结构化资源计划；
- 创建、协调并回收 Worker；
- 收集验证和审核结果；
- 请求 Backend 正式发布；
- 向学生汇报结果和下一步建议。

普通问答、简单课程解释和单纯刷新 `/learning-effects` 时不强制创建 Team。

#### Worker：资源生成 Agent

使用 `SubAgentTemplate(type="resource_generator")`。负责根据计划生成一个或多个资源草案并通过 `TeamSay` 汇报。它可以复用多种专用工具，但不能发布资源或批准自己的输出。

#### Worker：审核 Agent

使用 `SubAgentTemplate(type="resource_reviewer")`。负责读取计划、草案、课程引用和脱敏验证报告，输出结构化审核结论并通过 `TeamSay` 汇报。它不能修改草案、运行任意代码或正式发布。

### 6.3 动态协作与发布硬约束

Agent Team 不应退化成前端或 Backend 固定选择的工作流。前端只传自然语言目标和可信业务上下文，Leader 在允许的工具范围内决定是否创建 Worker。

但正式持久化属于业务硬约束：

```text
缺少确定性 validation_report
或缺少 reviewer 的 review_decision
  -> Backend 拒绝发布正式资源
```

因此 Leader 可以动态协调，但不能绕过正式发布前置条件。

## 7. 工具与权限白名单

### 7.1 通用规则

每个 Tool 必须同时满足：

1. 注册到对应 Agent 的 Toolkit/ToolGroup；
2. 加入该角色 PermissionContext 白名单；
3. 标记只读或有副作用；
4. 对有副作用工具设置明确权限；
5. 具备允许、拒绝和配置漂移测试。

测试必须验证：

- Toolkit 中存在但白名单缺失的工具不能执行；
- 白名单声明但 Toolkit 未注册时测试失败；
- 不同 Worker 不会继承不属于本角色的工具；
- 危险 shell/exec 工具默认拒绝。

### 7.2 角色工具边界

学情规划 Leader 允许读取学情、近期答题、课程 RAG、Team 工具、计划工具和发布请求工具；不得直接写 MySQL。

资源生成 Worker 允许课程 RAG、Markdown/Mermaid 草案、结构化练习草案和代码题草案工具；不得拥有正式发布、删除资源或修改学情事实的权限。

审核 Worker 只允许读取学情计划、资源草案、引用和脱敏验证报告，并提交审核结论；不得拥有通用 OJ、草案修改、隐藏用例读取或发布工具。

自定义 `SubAgentTemplate` 应禁止无意继承 Leader 的完整权限和工作目录。实施前必须针对本地 2.0.3 验证 `extend_leader_permission_rules`、`extend_leader_working_directories` 和 `override_leader_mode` 的真实行为，再确定最终参数组合。

## 8. 确定性验证与宽松审核

### 8.1 验证层不是 Agent

Markdown、Mermaid、结构化题目、代码编译和固定用例执行由确定性工具或 Backend 服务完成，不计作 Agent。生成 Worker 不得自证正确，审核 Worker 也不在内部实现 OJ。

代码题链路为：

```text
生成 Worker 产生草案
  -> Backend/OJ 验证参考解和固定输入
  -> 返回 validation_id 和脱敏报告
  -> 审核 Worker 作出审核结论
  -> Leader 请求发布
  -> Backend 原子写入正式题目与个性化资源关联
```

参考解和隐藏输入只能存在于 Backend 权威边界和受控验证请求中，不得进入前端、公开 SSE、Workspace artifact 或普通日志。

### 8.2 硬拒绝条件

只有明确、可验证的问题阻止发布：

- Schema 或必填字段不合法；
- 语言不在支持白名单；
- 缺少至少一个公开输入或一个隐藏输入；
- 固定测试输入重复；
- 参考解编译、运行、超时或任一固定用例失败；
- Markdown/Mermaid 无法通过确定性格式验证；
- 内容与课程引用存在明确关键事实冲突；
- 资源与请求目标完全无关；
- 参考解、隐藏输入、其他学生数据或敏感信息泄露；
- 违反内容安全硬规则。

### 8.3 非阻塞建议

以下只产生 `approved_with_advice`，默认不阻止发布：

- 可以增加更多边界用例；
- 题干或样例解释可以更清晰；
- 难度可能略高或略低；
- 内容组织和视觉层次可以改善；
- 测试覆盖比较基础但已满足确定性最低标准。

审核 Agent 不使用主观的“测试是否充分”作为硬门槛。一次资源最多允许一次定向返修，防止无限生成—审核循环。

审核结果结构：

```json
{
  "decision": "approved | approved_with_advice | rejected",
  "hard_failures": [],
  "warnings": [],
  "validation_id": "opaque-id",
  "reviewed_at": "ISO-8601 timestamp"
}
```

## 9. 业务数据与 Workspace 边界

AgentScope Workspace 保存运行期文件、草案和可回放 artifact，不是业务权威数据库。

Backend MySQL 保存：

- Evaluation 学情快照；
- 正式公共资源；
- 正式个性化资源关联；
- 正式练习题和代码题；
- 异步任务、验证状态和审核状态；
- 来源、课程归属和用户归属。

Agent Service 不直接写 MySQL。它只能通过 Backend 内部 HTTP 工具提交草案、验证请求、审核结论和发布请求。Backend 校验当前用户、课程、会话、validation_id 与 review_decision 的一致性后执行事务。

## 10. API 与事件边界

### 10.1 外部请求

AI Chat 和个性化资源页都发送自然语言目标，不发送决定固定 Agent 路由的 `intent` 或资源工作流枚举。可信的 `user_id`、`course_id`、`catalog_id`、conversation/session 标识由 Backend 注入或校验。

个性化资源页可以提供资源偏好，但偏好只作为 Leader 的提示，不绕过其规划过程。

### 10.2 EDU 事件适配

AgentScope 原生 AgentEvent 必须通过适配层转换为稳定 EDU 事件。建议使用：

- `workflow_started`
- `agent_started`
- `agent_message`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `source_refs`
- `artifact_created`
- `critic_completed`
- `plan_updated`
- `text_delta`
- `workflow_completed`
- `workflow_failed`

每个事件至少带有 `run_id`、`conversation_id`、`seq`、`timestamp`、`agent/role`、`type` 和稳定 payload。Frontend 不依赖 `TeamCreate`、`HintBlockEvent` 或其他 AgentScope 私有结构。

### 10.3 任务与失败

正式资源生成使用异步任务。失败必须区分：

- 学情事实不可用；
- RAG 证据不足；
- 生成失败；
- 确定性验证失败；
- 审核硬拒绝；
- 发布事务失败；
- Team session 或消息总线失败。

部分资源成功时任务可标记 `partial`，成功资源正常发布，失败资源保留可解释原因。不得因单个 Markdown 草案失败回滚已经独立验证并审核通过的其他资源，代码题自身的题目、用例和个性化关联仍必须保持原子提交。

## 11. 前端交互

### 11.1 个性化资源中心

保留现有页面并升级为统一中心，展示：

- 来源；
- 资源类型；
- 对应知识点；
- 生成状态；
- 审核状态或非阻塞建议；
- 创建时间；
- 打开、练习或删除操作。

### 11.2 主动生成入口

旧复选框弹窗改为独立智能生成页面或足够容纳全过程的面板。核心输入是自然语言需求，章节、知识点、资源偏好和难度为可选提示。

页面应展示稳定 EDU 事件映射出的：

- 学情读取；
- 资源计划；
- Worker 状态；
- 工具验证状态；
- 审核结论；
- 已发布资源。

不得直接渲染 AgentScope 原生 Team 对象。

### 11.3 `/learning-effects`

页面继续展示 Backend 保护的掌握事实和学情总结。增加“根据当前薄弱点生成资料”时，应预填一段自然语言需求并要求学生确认，不自动后台生成。

## 12. 迁移策略

本项目当前工作树包含广泛未提交修改，实施必须分批、测试驱动推进，不得在 `leader_team.py` 上继续堆叠新分支。

### 阶段一：修复事实与语义

- 修复学习效果事实聚合；
- 修订公共资源类型与全 KG 节点策略；
- 为现有数据定义兼容映射或迁移；
- 不改变 AI Chat 主链。

### 阶段二：统一业务持久化

- 定义个性化资源草案、validation 和 review 业务协议；
- AI Chat artifact 保存到 Backend；
- 个性化资源页展示统一来源和状态；
- 保持 Agent Service 不写 MySQL。

### 阶段三：接入官方 Agent Team

- 评估并配置 `create_app` 所需 Storage、MessageBus 和 WorkspaceManager；
- 注册 `resource_generator` 和 `resource_reviewer` 模板；
- 建立角色白名单和权限测试；
- 建立 AgentScope Event 到 EDU Event 的适配；
- 用官方 Team 替代资源生成主链中的伪 Team。

### 阶段四：统一交互入口

- 个性化资源页切换到自然语言智能生成入口；
- AI Chat 与手动入口复用相同 Leader/Team 能力；
- `/learning-effects` 增加用户确认式生成建议；
- 完成赛题演示链和可观测团队 UI。

旧链路在新链路通过集成验证前保持可运行。迁移完成后再单独设计删除范围，不在本设计中直接删除旧代码。

## 13. 测试策略

### 13.1 Backend

- 学情事实聚合单元测试；
- 最近趋势、资源实际使用和章节进度回归测试；
- 用户、课程和 Catalog 权限测试；
- 草案、validation、review 与发布状态机测试；
- 代码题原子提交和隐私测试；
- Webhook/内部 API 契约测试；
- 部分成功与失败恢复测试。

### 13.2 Agent Service v2

- AgentScope 2.0.3 版本与 API 冒烟测试；
- `SubAgentTemplate` 权限隔离测试；
- Toolkit 与白名单一致性测试；
- Leader 创建 Worker、Worker `TeamSay` 和 Team 清理集成测试；
- 确定性验证报告脱敏测试；
- 审核硬拒绝与软建议测试；
- 最大迭代、超时和一次返修上限测试；
- AgentEvent 到 EDU Event 适配测试；
- 正式 Agent Team 入口集成测试，不能只断言类或 import 存在。

### 13.3 Frontend

- 五类资源和来源展示测试；
- Team/工具/审核事件 UI 测试；
- 生成中、部分成功、失败和重试状态测试；
- AI Chat 保存后出现在个性化资源中心的集成测试；
- `/learning-effects` 建议生成需用户确认的交互测试；
- lint 和 production build。

## 14. 架构模式取舍

### 14.1 选用

- **Agent Team**：三个角色具有真实独立 Session、权限和事件流；
- **策略/工具注册模式**：不同资源格式由 typed tools 承担，避免资源类型分支堆积；
- **适配器模式**：隔离 AgentScope AgentEvent 与 EDU SSE；
- **快照模式**：复用 Evaluation，避免每次生成重复且漂移的学情分析；
- **状态机/发布门槛**：确保草案、验证、审核和发布顺序；
- **Backend Service 分层**：业务事务和 MySQL 持久化留在 Backend service。

### 14.2 不选用

- **每种资源一个 Agent**：角色过多，协作收益不足；
- **前端固定工作流**：违反 Agent 动态路由目标；
- **Agent 直接写数据库**：违反服务边界；
- **纯自由文本 Agent 协议**：难以验证、重放和迁移；
- **审核 Agent 自行实现 OJ**：推理与确定性执行边界错误；
- **公共和个性化资源共用一个业务生成协议**：容易泄露学生私有上下文。

## 15. 验收标准

1. 公共资源不再限制为最多十个节点，覆盖全部有效 KG 节点；
2. 公共资源类型与实际内容一致，不再出现伪 `code` 或 HTML 冒充文档；
3. `/learning-effects` 使用真实章节进度、近期趋势和学生资源使用数据；
4. AI Chat、主动生成和错题强化结果都能出现在统一个性化资源中心；
5. 系统正式支持五类个性化资源；
6. 一次正式个性化资源生成能观察到 Leader、生成 Worker 和审核 Worker 的独立 Session/事件；
7. 官方 Team 工具和 `SubAgentTemplate` 在实际入口中运行，而非只存在于测试或文档；
8. 每个角色只能调用其白名单工具，配置漂移由测试阻止；
9. 代码题只有在 OJ 确定性验证通过且取得审核结论后才能发布；
10. 审核软建议不会阻止正常资源发布，硬拒绝范围明确且最多返修一次；
11. 参考解、隐藏用例和其他学生数据不会出现在前端、SSE、Workspace artifact 或普通日志；
12. Frontend 和 Backend 只依赖稳定 EDU 协议，不依赖 AgentScope 私有事件对象；
13. Agent Service 不写 MySQL，Backend 不访问 Qdrant，前端不直连 Agent Service；
14. 相关单元、契约、事件适配和端到端测试通过。

## 16. 设计后的实施约束

本设计涉及数据结构、Agent Team 托管、内部协议、多个页面和核心 service，属于大改。实施前必须另行编写分阶段实施计划。每个阶段应控制在可验证、可回滚的边界内，先写失败测试，再做最小实现。

任何 Client API 或 Agent API 字段、枚举、同步行为或路径变化都必须在实施计划中逐项列出，并同步更新调用双方和 `WorkLine.md`。未经单独确认，不引入新依赖、不修改 `.env`、不删除旧运行链路、不提交用户数据或生成产物。
