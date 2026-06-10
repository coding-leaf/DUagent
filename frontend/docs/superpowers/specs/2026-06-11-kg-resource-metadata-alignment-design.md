# KG 资源生成 Metadata 与节点对齐设计

日期：2026-06-11

## 背景

Route A 可用支撑阈值版本已经生成 active KG。真实 C 语言样本当前 active KG 为 `route_a_prune_usable_060`，节点结构比旧 Route A 明显改善：

- `108/116` nodes kept。
- `100` edges。
- support bands 为 `strong=57`、`good=34`、`weak_but_usable=17`、`unsupported=8`。

但 KG-Resource 对齐探针仍然 `108/108` 节点 `candidate_count=0`。只读核验显示当前生成资源的 metadata 全部是：

- `chapter=课程整体`
- `knowledge_point=综合知识点`

而 LearningPath 节点资源接口和探针使用精确字段匹配：

- `Resource.knowledge_point == node_name`
- `Resource.chapter == chapter`

因此当前阻塞不是 active KG 未生效，而是资源生成时没有把资源写到 KG 标准章节和知识点体系上。

## 目标

第一版目标是让 Admin 资源库级资源生成在未显式指定 `chapter/knowledge_point` 时，自动围绕 active KG 的核心节点生成资源，并把 KG 标准 metadata 写入 `resources` 表。

具体目标：

1. 资源生成默认能从 active KG 选择核心节点子集。
2. Agent 生成请求使用 KG 节点的 `chapter` 和 `name` 作为现有 `chapter/knowledge_point` 字段。
3. Webhook 落库时强制使用 Backend 记录的目标节点 metadata，防止 Agent 输出漂移。
4. 现有 LearningPath 节点资源接口无需改造即可通过精确匹配命中资源。
5. KG-Resource 对齐探针能从零命中变为核心节点有真实候选。

## 非目标

本轮不做：

- 不改 Client API / OpenAPI。
- 不改 Agent API / OpenAPI。
- 不新增前端 UI 或 KG 选择控件。
- 不让 Admin 手动选择 KG 版本或节点。
- 不新增 `resource_kg_node_mappings` 映射表。
- 不做一个资源挂多个节点。
- 不生成全量 KG 节点资源。
- 不做 KG ready gate。
- 不做 LearningPath refresh UI。
- 不用 mock 或假数据掩盖真实资源缺口。

## 方案选择

采用推荐方案：Backend 读取课程 active KG，选择核心 KG 节点子集，再复用现有 Agent 单目标资源生成接口。

不采用扩展 Agent `target_nodes[]` 的方案，因为它会修改 Agent API 契约、schema、Backend payload 和 OpenAPI，当前阶段边界过大。

不采用第一版映射表方案，因为现有匹配链路已经依赖 `Resource.chapter/knowledge_point`，当前问题的直接根因也是这两个字段过于泛化。先修正生成时 metadata，可以最小改动验证链路是否成立。后续如果需要一个资源挂多个 KG 节点，再单独设计映射表。

## 架构设计

KG 仍由 CLI 生成并写入 `course_knowledge_graphs`。资源生成入口不新增 KG 参数，也不让前端选择 KG。

Admin 调用：

```http
POST /api/v1/admin/course-catalogs/{catalog_id}/resources/generations
```

Backend 行为：

1. 如果请求显式包含 `chapter` 或 `knowledge_point`，保持现有单目标生成语义。
2. 如果请求没有显式包含 `chapter/knowledge_point`，进入 KG-node 模式。
3. KG-node 模式读取该 catalog 绑定的 teaching class 对应 course active KG。
4. Backend 从 active KG 中选择核心节点子集。
5. Backend 对每个目标节点调用现有 Agent `/agent/v1/resources/generate`，请求体仍只使用现有字段：

```json
{
  "task_id": "child-task-id",
  "user_id": "admin-user-id",
  "course_id": "catalog-id",
  "chapter": "KG 节点 chapter",
  "knowledge_point": "KG 节点 name",
  "resource_types": ["document", "mindmap", "reading", "code"],
  "webhook_url": "http://backend.example/api/v1/webhooks/agent"
}
```

Agent 继续根据 `course_id` 检索 CourseCatalog 知识库，根据 `chapter/knowledge_point` 生成资源。Backend 不直接访问 Qdrant，Agent Service 不写 Backend SQL。

## 核心节点选择

第一版选择算法必须确定性执行，不让 AI 自行决定挂载节点。

默认规则：

- 数据源：active KG。
- 默认目标数量：`10` 个节点。
- 可选节点：active KG kept nodes。
- 排除节点：`unsupported` 或无有效 `name/chapter` 的节点。
- 优先级：`strong` > `good` > `weak_but_usable`。
- 不优先选择 `weak_but_usable`，仅在 strong/good 不足时补齐。
- 去重键：`chapter + node_name`。
- 章节均衡：按 chapter 分组轮询取节点，避免核心节点集中在单一章节。
- 排序信号：优先使用节点 grounding 分数；如果 active KG nodes 没有携带节点级分数，则按 support band、KG 原始顺序和章节均衡兜底。

如果当前 active KG 没有节点级 support band 字段，Backend 可从 KG `metrics` 中已有 grounding/pruned detail 或节点附带字段中读取；如果都没有，只能使用 KG 顺序和章节均衡兜底，同时在父任务 `result.selection_degraded=true` 中记录原因。

本轮不新增前端参数调整目标数量。后续如需配置化，可以先放 Backend 内部常量。

## 任务模型

采用“父任务对前端可见，子任务内部承接 Agent 回调”的结构。

父任务：

- `task_type=resource_generation`
- 前端只轮询父任务。
- `course_id=None`
- `result.mode=kg_node_targets`
- 保存 catalog、fan-out course ids、目标节点列表和聚合结果。

父任务 `result` 示例：

```json
{
  "catalog_id": "b2444963f0e54587",
  "catalog_title": "C 语言",
  "fanout_course_ids": ["6c698badb60a4809"],
  "mode": "kg_node_targets",
  "target_node_count": 10,
  "resource_types": ["document", "mindmap", "reading", "code"],
  "target_nodes": [
    {
      "node_id": "pointer_array",
      "node_name": "指针与数组",
      "chapter": "第八章 指针",
      "support_band": "good",
      "body_top1_score": 0.68
    }
  ]
}
```

子任务：

- `task_type=resource_generation`
- 使用独立 `task_id` 调 Agent，避免多个 Agent 回调复用父任务 id 导致 webhook 幂等冲突。
- `result.parent_task_id` 指向父任务。
- `result.target_node` 保存标准 KG metadata。
- `result.fanout_course_ids` 继承父任务。
- 默认不作为前端任务入口展示。

子任务 `result` 示例：

```json
{
  "catalog_id": "b2444963f0e54587",
  "parent_task_id": "parent-task-id",
  "fanout_course_ids": ["6c698badb60a4809"],
  "mode": "kg_node_target",
  "target_node": {
    "node_id": "pointer_array",
    "node_name": "指针与数组",
    "chapter": "第八章 指针",
    "support_band": "good",
    "body_top1_score": 0.68
  },
  "resource_types": ["document", "mindmap"]
}
```

父任务聚合规则：

- 所有子任务完成后，父任务 `completed`。
- 至少一个子任务成功、部分失败时，父任务仍 `completed`，但 `result.degraded=true`。
- `result.successful_node_count` 和 `result.failed_node_count` 必须记录。
- 所有子任务失败时，父任务 `failed`。
- 子任务 webhook 结束后触发父任务状态重算；如果当前实现不引入异步 worker，可在 webhook 同一事务后重算父任务。

## Webhook 落库规则

现有 webhook 校验仍要求 Agent 返回：

- `title`
- `type`
- `description`
- `content`
- `chapter`
- `knowledge_point`
- `tags`

KG-node 模式下，Backend 落库时不得信任 Agent 返回的 `chapter/knowledge_point` 作为最终挂载字段。最终落库规则：

```text
Resource.chapter = task.result.target_node.chapter
Resource.knowledge_point = task.result.target_node.node_name
```

如果不是 KG-node 子任务，保留现有行为，使用 Agent 返回字段。

tags 可以追加内部诊断信息，例如：

```json
["第八章 指针", "指针与数组", "document", "kg_node:pointer_array", "support_band:good"]
```

tags 不是匹配主键，不作为节点挂载的唯一依据。

## 资源可见性

第一版继续沿用当前 fan-out 持久化：

1. Backend 查询 catalog 当前绑定的非删除 teaching classes。
2. 每个 Agent 生成资源写入每个绑定 class 对应的 `Resource.course_id`。
3. 学生和教师继续通过现有 `GET /resources` 按 teaching class 读取资源。

新绑定到 catalog 的 class 不自动回填历史生成资源；这与当前 CourseCatalog fan-out 设计一致。

## 错误处理

没有 active KG：

- 父任务失败。
- 错误说明为“课程知识图谱未就绪”。
- 不回退到 `课程整体/综合知识点`。

active KG 没有可选节点：

- 父任务失败。
- 错误说明为“没有可用于资源挂载的 KG 节点”。

Agent 部分失败：

- 父任务 `completed`。
- `result.degraded=true`。
- 记录成功节点、失败节点和失败原因。

Agent 全部失败：

- 父任务 `failed`。

Agent 返回 metadata 与目标节点不一致：

- Webhook 仍可通过基础字段校验。
- 落库使用子任务 `target_node` 覆盖挂载 metadata。

显式 `chapter/knowledge_point` 请求：

- 完全保留现有行为。
- 不进入 KG-node 模式。

## 探针与 LearningPath 影响

现有 LearningPath 节点资源接口可以不改：

- `weak_point_tutorials` 通过 `Resource.knowledge_point == node_name` 命中。
- `chapter_materials` 通过 `Resource.chapter == chapter` 命中。

现有 KG-Resource 对齐探针也可以不改：

- `candidate_resource_ids` 会从当前零命中变为核心节点非零候选。
- 仍可通过人工标注判断命中资源是否真正相关。

本轮完成后仍不能直接推进 KG ready gate。必须先重跑正式 KG-Resource probe，确认核心节点资源候选质量。

## 测试设计

Backend 单元/集成测试：

1. 核心节点选择：
   - strong/good 优先于 weak。
   - unsupported 不被选择。
   - 章节均衡生效。
   - 目标数量上限生效。
   - `chapter + node_name` 去重生效。

2. Admin 生成入口：
   - 请求不传 `chapter/knowledge_point` 时进入 KG-node 模式。
   - 请求显式传 `chapter/knowledge_point` 时保持现有单目标行为。
   - 无 active KG 时不创建无效 Agent 调用。
   - 无可选节点时不创建无效 Agent 调用。

3. Agent payload：
   - 每个子任务调用 Agent 时传入 KG 节点 `chapter` 和 `node_name`。
   - `course_id` 仍传 catalog id，供 Agent 检索 CourseCatalog 知识库。
   - 子任务 `task_id` 独立。

4. Webhook 落库：
   - KG-node 子任务落库时使用 `target_node` 覆盖 Agent 返回 metadata。
   - 非 KG-node 任务保留现有 Agent 返回 metadata。
   - fan-out 到所有绑定 class。

5. 父任务聚合：
   - 全部子任务成功时父任务 completed。
   - 部分失败时父任务 completed 且 degraded。
   - 全部失败时父任务 failed。

Agent Service 测试：

- 原则上不需要修改 Agent API。
- 如果实现过程中发现 Agent 某条生成路径没有稳定回填请求 `chapter/knowledge_point`，只补 Agent 内部测试和实现，不扩展请求/响应契约。

真实验证：

1. 对当前 C 语言 catalog/course 使用 active KG 触发资源生成。
2. 只生成核心节点子集，不生成全量 108 节点。
3. 重跑 KG-Resource inventory 和 probe。
4. 验收重点：
   - `candidate_count>0` 的节点不再为 0。
   - 核心节点候选资源的 `chapter/knowledge_point` 与 KG 节点一致。
   - 抽样人工检查资源内容与节点语义相关。

## 成功判据

实现层：

- 不改 Client API / Agent API。
- 显式 `chapter/knowledge_point` 生成兼容旧行为。
- 默认 Admin catalog resource generation 能进入 KG-node 模式。
- Webhook 对 KG-node 子任务强制使用标准 KG metadata 落库。

数据层：

- 当前 C 语言样本重新生成后，KG-Resource probe 不再 `108/108 candidate_count=0`。
- 核心节点中至少出现稳定非零候选。
- 无效泛化 metadata 不再作为默认生成结果继续扩大。

决策层：

- 如果核心节点候选质量通过人工抽查，下一步评估 LearningPath 读取 active KG 的节点资源挂载结果。
- 如果候选非零但人工质量差，下一步不是 KG ready gate，而是改资源内容生成质量或节点选择策略。
- 如果仍然零命中，说明实现没有把 KG metadata 写入落库字段，必须回到 webhook/任务链路排查。

## 后续演进

映射表后置到以下真实需求出现后再设计：

- 一个资源需要挂多个 KG 节点。
- 节点别名、同义词或跨章节复用导致精确字段匹配不足。
- 需要按 node_id 而不是 `chapter/name` 做稳定引用。
- 需要保存匹配置信度、来源、人工审核状态。

如果进入映射表方案，应单独设计 schema、迁移、节点资源接口优先级、探针逻辑和历史资源回填策略。
