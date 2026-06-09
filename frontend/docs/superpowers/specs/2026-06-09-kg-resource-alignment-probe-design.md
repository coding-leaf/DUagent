# KG-Resource 对齐探针评估设计

## 目标

本 spec 定义一轮上线前评估：判断当前 `KG 节点 -> 真实资源/题目` 的挂载规则是否可靠到足以支撑后续 `LearningPath` 刷新上线。

这不是学术准确率评估，也不是直接改 UI 或改匹配算法。目标是先用真实数据证明当前精确字段匹配到底能不能用；如果不能用，要明确卡在什么错配类型上，再决定是否进入语义匹配、别名表、字段规范化或 Agent 输出对齐等实现分支。

## 当前代码事实

以下事实已按当前代码核实：

- `CourseKnowledgeGraph` 是课程静态知识图谱，表为 `course_knowledge_graphs`，字段包含 `course_id`、`nodes`、`edges`。Backend 注释说明它会作为 Agent `/learning-path/generate` 的 `knowledge_graph.nodes/edges` 输入（`../backend/app/models/others.py:114`）。
- `LearningPath` 是用户和课程维度的生成结果，表为 `learning_paths`，字段包含 `user_id`、`course_id`、`nodes`、`edges`、`current_node_id`、`current_node_name`（`../backend/app/models/others.py:97`）。
- 当前节点资源接口是 `GET /api/v1/learning-path/nodes/{node_id}/resources?course_id=...`（`../backend/app/api/v1/learning_path.py:306`）。
- 该接口从最新 `LearningPath.nodes` 中取 `node_name`，从 `CourseKnowledgeGraph.nodes` 中取 `chapter`（`../backend/app/api/v1/learning_path.py:335`、`:353`）。
- 该接口用精确相等匹配真实内容：
  - `Resource.knowledge_point == node_name` 生成 `weak_point_tutorials`（`../backend/app/api/v1/learning_path.py:369`）。
  - `QuizQuestion.knowledge_point == node_name` 生成 `exercises`（`../backend/app/api/v1/learning_path.py:386`）。
  - `Resource.chapter == chapter` 生成 `chapter_materials`（`../backend/app/api/v1/learning_path.py:403`）。
- 当前返回结构没有 `rank`、`score` 或 `similarity` 字段，也没有显式排序依据；相关查询没有 `order_by`。因此本轮不能使用“候选前 1/3/5 位”或排序质量作为评估口径。

由此可见，`KG ready` 不等于 `挂载可信`。如果 KG 已存在但节点名、章节名与资源字段不一致，当前接口仍可能挂不上真实内容。因此 `KG ready gate` 之前必须先做 KG-Resource 对齐探针。

## 评估范围

评估对象是当前精确字段匹配规则，不评估 Agent 生成路径质量本身。

本轮只看：

- KG / LearningPath 节点是否能通过当前规则命中真实 `Resource`。
- KG / LearningPath 节点是否能通过当前规则命中真实 `QuizQuestion`。
- 未命中是否主要因为“语义其实对得上，但字段文字不一致”。

本轮不做：

- 新增语义匹配。
- 新增排序分数。
- 新增 KG ready gate。
- 新增 LearningPath refresh UI。
- 修改 OpenAPI、Backend、Agent 或前端页面。

当前接口返回的 `full_exercise_set` 是课程全量题目兜底集合，不是按节点匹配的挂载结果。它不参与节点级命中判定，不计入 `candidate_count`，只可作为页面附带内容单独记录。

## 第 0 步：数据底盘盘点

正式探针前必须先盘点现有数据，确认是否存在足量第二样本。

盘点每个真实 catalog / course 组合：

- `catalog_id`。
- 已绑定 `course_id`。
- `chunk_count`。
- KG 节点数。
- LearningPath 节点数。
- 非删除资源数。
- distinct `Resource.knowledge_point` 数。
- distinct `Resource.chapter` 数。
- 非删除题目数。
- distinct `QuizQuestion.knowledge_point` 数。

第二轮正式样本必须满足：

- KG 或 LearningPath 节点数足以抽取 `10-15` 个核心节点。
- 非删除资源或题目数量足以支持人工判断。
- 资源或题目至少存在可匹配的 `knowledge_point` 或 `chapter` 元数据。

如果盘点后不存在合格的第二个 catalog，本轮不能输出 `go/no-go`。结论应写为：`数据量不足以评估；上线前置是补充或构造足量真实样本`。此时只能执行 `89f51dfbdedc4995` 的流程校准，不能推进 `KG ready gate`。

## 样本策略

评估分三轮，顺序固定：

1. 已验收 catalog：`89f51dfbdedc4995`。
   - 目的：校准探针流程，确认数据抽取、人工标注、错配记录能跑通。
   - 样本：全量取它实际拥有的 KG / LearningPath 节点。
   - 限制：该 catalog `chunk_count=1`，预计节点数很少，不产汇总命中率，不单独出 `go/no-go`。

2. 内容更杂、chunk 更多的真实 catalog。
   - 目的：作为正式对齐结论来源。
   - 前提：第 0 步盘点确认存在满足条件的第二样本。
   - 样本：抽取 `10-15` 个核心节点。
   - 核心节点定义必须客观：
     - 默认使用 chunk 覆盖密度、知识点在资料中的出现频次、distinct resource coverage 作为代理指标。
     - 如果项目已经存在真实访问 / 命中埋点，再优先使用学生实际访问或命中过的节点；没有埋点时不强求行为数据。

3. 最近新鲜入库的真实 catalog。
   - 目的：贴近上线场景做压力测试。
   - 样本：沿用第二轮的核心节点抽取规则。
   - 结论：用于验证第二轮结论是否可迁移，不替代第二轮的主结论。

## 人工标注口径

“正确资源”由人工裁定。最小判据是：人阅读节点名、章节和资源标题 / 摘要 / 正文后，是否会认为该资源应该挂在这个 KG / LearningPath 节点下。

一个节点可以有多个正确资源。命中判定如下：

- `matched=true`：当前精确匹配结果至少命中 1 个人工标注的正确资源或题目。
- `matched=false`：当前精确匹配结果没有命中任何人工标注的正确资源或题目。

即使 `matched=true`，也必须记录：

- `expected_correct_count`：人工认为应命中的资源 / 题目数量。
- `actual_matched_correct_count`：当前规则实际命中的正确资源 / 题目数量。
- `candidate_count`：当前接口返回的候选数量。

这样保留部分命中信息，避免“至少命中 1 个”掩盖召回不足。

## 节点级记录表

每个被评估节点记录以下字段：

| 字段 | 含义 |
| --- | --- |
| `catalog_id` | 资源库 id |
| `course_id` | 教学班 id |
| `node_id` | KG / LearningPath 节点 id |
| `node_name` | 节点名 |
| `chapter` | KG 节点章节 |
| `candidate_resource_ids` | 当前规则返回的资源候选 |
| `candidate_quiz_ids` | 当前规则返回的题目候选 |
| `candidate_count` | 当前候选总数 |
| `expected_correct_ids` | 人工标注应命中的资源 / 题目 |
| `expected_correct_count` | 人工标注应命中数量 |
| `actual_matched_correct_ids` | 实际命中的正确资源 / 题目 |
| `actual_matched_correct_count` | 实际命中正确数量 |
| `matched` | 是否至少命中 1 个正确项 |
| `mismatch_type` | 未命中或部分命中的错配类型 |
| `human_judgement_note` | 人工判断说明，简短写明为什么该资源应挂或不应挂 |

## 错配类型

错配类型使用封闭清单，必要时用 `other` 兜底。不得自由发挥新标签，否则不同节点无法聚合。

| 类型 | 含义 |
| --- | --- |
| `exact_match_ok` | 精确字段匹配命中，且人工认为合理 |
| `semantic_text_mismatch` | 语义应挂载，但 `node_name` 与 `knowledge_point` 或 `chapter` 字面不一致导致未命中 |
| `chapter_mismatch` | 知识点语义相关，但章节字段不一致导致章节资料未命中 |
| `resource_metadata_missing` | 资源存在，但缺 `knowledge_point` 或 `chapter` 等可匹配元数据 |
| `kg_node_too_broad` | KG 节点过宽，人工无法稳定判断应挂哪些资源 |
| `kg_node_too_narrow` | KG 节点过窄，资料里没有可对应的具体资源 |
| `resource_content_irrelevant` | 当前规则命中了候选，但人工认为内容不该挂该节点 |
| `no_real_resource` | 该节点当前确实没有对应真实资源或题目 |
| `other` | 以上类型无法覆盖，必须在 `human_judgement_note` 写原因 |

## 汇总指标

正式汇总只对第二个内容更杂、节点数足够的 catalog 输出。`89f51dfbdedc4995` 不输出汇总命中率和 `go/no-go`。

汇总字段：

- 节点数。
- `matched` 节点数。
- 精确未命中率：`matched=false` 的节点数 / 总节点数。
- 平均候选数。
- 平均应命中数量。
- 平均实际命中正确数量。
- 错配类型分布。
- `semantic_text_mismatch` 在未命中节点中的占比。

## Go / No-Go 阈值

阈值必须在跑探针前固定，不能跑完后倒推。

第二个 catalog 的判定规则：

- `go`：
  - 精确未命中率 `<= 30%`。
  - 且未命中节点中，`semantic_text_mismatch` 占比 `<= 50%`。
  - 且没有集中出现单一阻塞类型（`semantic_text_mismatch` 除外）超过未命中节点的 `70%`。

- `no-go`：
  - 精确未命中率 `> 30%`。
  - 或未命中节点中，`semantic_text_mismatch` 占比 `> 50%`。
  - 或单一阻塞类型（`semantic_text_mismatch` 除外）超过未命中节点的 `70%`。

解释：

- 精确未命中率高，说明当前挂载规则整体不可依赖。
- 未命中里大量是 `semantic_text_mismatch`，说明资源语义本身可能对，但精确相等不适配 KG 挂载，后续应进入语义匹配、别名表、字段规范化或 Agent 输出对齐分支。
- 如果除 `semantic_text_mismatch` 以外的单一阻塞类型高度集中，说明问题可定位，但上线前仍需要先处理该阻塞，不应直接做 KG ready gate。

## 决策分支

探针完成后只允许进入以下分支：

1. 精确匹配可用。
   - 条件：第二个 catalog 判定为 `go`。
   - 下一步：再写 `KG ready gate` spec，重点定义 KG 有无、过期、错误码、降级策略和前端提示。

2. 精确匹配不适配。
   - 条件：第二个 catalog 判定为 `no-go`，且 `semantic_text_mismatch` 是主要原因。
   - 下一步：先设计挂载策略改造，不写 KG ready gate。候选方向包括语义匹配、别名表、字段规范化、Agent 生成时强制使用 KG 节点标准名。

3. 数据质量不足。
   - 条件：第二个 catalog 判定为 `no-go`，但主要原因是 `resource_metadata_missing`、`kg_node_too_broad`、`kg_node_too_narrow` 或 `no_real_resource`。
   - 下一步：先处理 KG 或资源元数据质量，不把问题归因到匹配算法。

## 输出物

探针评估应产出：

- `89f51dfbdedc4995` 节点级记录表，用于证明探针流程能跑通。
- 第二个 catalog 的节点级记录表。
- 第二个 catalog 的汇总指标和 `go/no-go`。
- 错配类型分布。
- 下一步分支建议。

第三个新鲜入库 catalog 作为压力测试，在第二个 catalog 跑完并确认探针方法稳定后再执行。

## 验证边界

本 spec 的验收不是“LearningPath 刷新可上线”，而是“是否已经有证据判断当前 KG-Resource 精确挂载规则可用或不可用”。

如果探针未跑，或没有人工标注，不能声称 KG ready gate 可以推进。
