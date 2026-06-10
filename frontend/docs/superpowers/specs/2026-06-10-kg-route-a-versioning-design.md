# KG 版本化与路线 A 生成返工设计

日期：2026-06-10

## 背景

上一轮只读探针已经证明：当前 CLI 生成的 KG 主要复刻目录 / 大纲，而不是由正文内容稳定支撑。

样本：

- catalog_id：`b2444963f0e54587`
- course_id：`6c698badb60a4809`
- 课程：`C语言`
- 当前 CLI KG：`116` 节点、`115` 边

关键结果：

- 排除目录型 chunk 后，`body_top1_score >= 0.70` 的节点只有 `25/116 = 21.6%`。
- 剔除目录后正文 chunk 仍有 `613` 个，其中知识型正文 `465/613 = 75.9%`。
- 资料足够厚，问题在 KG 生成方式，不在资料缺失。

因此下一步不是审核 / 签字、KG ready gate、LearningPath 刷新 UI，也不是让资源立刻继承 KG 节点名；下一步是先做 KG 版本 / 回滚，再按路线 A 返工生成逻辑。

## 已核实的当前代码事实

- `CourseKnowledgeGraph` 当前模型只有 `course_id/nodes/edges/create_time/update_time/is_deleted` 等字段，没有版本字段，也没有 active 标记（`../backend/app/models/others.py:114`）。
- `schema.sql` 当前对 `course_knowledge_graphs.course_id` 有唯一索引 `uk_course`，即每门课只能有一条未区分版本的 KG 记录（`../backend/schema.sql:383`、`../backend/schema.sql:393`）。
- `generate_knowledge_graph.py` 的写库函数会查询当前课程未删除 KG，存在则覆盖 `nodes/edges/update_time`，不存在才新增（`../backend/tools/generate_knowledge_graph.py:179`、`../backend/tools/generate_knowledge_graph.py:190`）。
- `import_knowledge_graph.py` 也采用同样的 upsert 覆盖方式（`../backend/tools/import_knowledge_graph.py:25`、`../backend/tools/import_knowledge_graph.py:36`）。
- LearningPath refresh payload 当前读取 `course_id` 下第一条未删除 KG，没有 active/version 过滤（`../backend/app/api/v1/learning_path.py:123`）。
- 学习路径节点资源接口查 chapter 时同样读取 `course_id` 下第一条未删除 KG，没有 active/version 过滤（`../backend/app/api/v1/learning_path.py:353`）。

## 成功判据

路线 A 写代码前固定唯一成功线：

> 新 KG 生成后，重跑 KG-to-body chunk 正文支撑对账探针；排除目录型 chunk 后，`body_top1_score >= 0.70` 的节点占比必须从当前 `21.6%` 提升到 `>= 70%`。

解释：

- 这是新造 KG 是否成功的工程验收线，不是学术准确率。
- 判据必须跑前固定，不能在生成后按观感倒推。
- 本判据只评价 KG 是否有正文支撑；资源挂载、审核、ready gate 是后续问题。

## 范围

本轮要做：

1. KG 版本 / 回滚基础设施。
2. 路线 A 第一版：目录给候选骨架，正文 chunk 验证候选节点；先砍掉无正文支撑节点。
3. 新 KG 生成后重跑正文支撑对账探针，按固定成功线判定。

本轮不做：

- 不做人工审核 / 签字流程。
- 不做 KG ready gate。
- 不做 LearningPath refresh UI。
- 不让资源生成继承 KG 节点名。
- 不做正文聚类补新节点。补新节点作为路线 A 第二步，等“砍掉无支撑节点”跑完再看缺口。
- 不引入 mock，不伪造 Qdrant chunk，不使用 SQLite。

## 版本 / 回滚设计

目标：每次 KG 生成保存成一个版本，LearningPath 默认只读取 active 版本；试坏时可以把 active 切回旧版本。

建议沿用 `course_knowledge_graphs` 表，不新增读取主表：

- 移除 `course_id` 唯一约束。
- 新增 `version`：同一 `course_id` 内递增。
- 新增 `is_active`：当前生效版本。
- 新增 `source_type`：如 `outline_llm`、`route_a_body_grounded`、`manual_import`。
- 新增 `generation_strategy`：如 `legacy_outline`、`route_a_prune_unsupported`。
- 新增 `metrics` JSON：保存 `body_top1_threshold`、`body_support_pass_ratio`、`kept_node_count`、`pruned_node_count` 等实验指标。
- 新增 `parent_graph_id`：记录本版本来源，便于回滚和对比。

读取规则：

- LearningPath refresh 和节点资源接口只读 `is_active=True` 且 `is_deleted=False` 的最新 KG。
- 如果历史数据没有 `is_active` 字段迁移值，迁移脚本将每门课现有记录设为 `version=1,is_active=True`。
- 同一课程同一时刻只能有一个 active KG。实现上在事务内先取消旧 active，再激活目标版本。

写入规则：

- `generate_knowledge_graph.py` 不再覆盖旧 KG，而是创建新版本。
- `import_knowledge_graph.py` 默认也创建新版本；如传入 rollback / activate 参数，只切 active，不改节点内容。
- 每次生成后返回 `course_id/version/graph_id/node_count/edge_count/is_active/metrics`。

## 路线 A 第一版

路线 A 第一版只做“目录候选节点的正文验证与裁剪”：

当前流程：

```text
读目录 -> LLM 生成 nodes/edges -> 结构校验 -> upsert 覆盖 KG
```

第一版目标流程：

```text
读目录 -> LLM 生成候选 nodes/edges -> 结构校验
-> 从 Qdrant 读取该 catalog 的正文 chunk，排除目录型 chunk
-> 每个候选节点取正文 chunk 最高相似度
-> body_top1_score >= 0.70 的节点保留
-> body_top1_score < 0.70 的节点裁剪
-> 裁剪悬空边
-> 创建新 KG 版本
-> 重跑正文支撑对账探针验收
```

裁剪规则：

- 节点级判断只看排除目录后的正文 chunk。
- 第一版阈值固定为 `body_top1_score >= 0.70`。
- 被裁剪节点不写入 active KG，但要写入本次版本的 `metrics.pruned_nodes` 摘要，便于复盘。
- 边只保留两端节点都存在的边。
- 如果裁剪后节点数为 0，生成失败，不创建 active KG。

为什么第一版不补新节点：

- 补新节点需要正文聚类或 LLM 归纳，会引入新的不确定性。
- 先裁剪能直接验证目录复刻水分是否能被挤掉。
- 裁剪后再看缺口，才能决定是否需要路线 A 第二步“正文补点”。

## 验收流程

1. 对当前 C 语言样本生成路线 A 新 KG 版本。
2. 确认旧目录版 KG 仍保留为历史版本，且可以回滚。
3. 确认 LearningPath 读取 active KG。
4. 重跑正文支撑对账探针。
5. 按固定成功线判断：
   - `body_top1_score >= 0.70` 的节点占比 `>=70%`：路线 A 第一版通过，可进入 KG-Resource 对齐复验。
   - 未达到 `>=70%`：路线 A 第一版不通过，继续分析被裁剪节点、正文缺口和是否需要正文补点。

## 后续决策门

只有当路线 A 新 KG 通过正文支撑探针后，才继续：

- KG-Resource 对齐探针。
- 资源生成是否继承 KG 节点名。
- KG ready gate。
- 审核 / 签字。
- LearningPath refresh UI。

如果路线 A 第一版未通过：

- 不推进审核 / ready gate。
- 不把失败 KG 固化到资源标签。
- 优先分析是阈值过严、目录候选缺失，还是需要路线 A 第二步“正文补点”。
