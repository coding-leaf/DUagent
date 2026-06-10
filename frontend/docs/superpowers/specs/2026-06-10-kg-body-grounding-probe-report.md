# KG 正文支撑对账探针报告

日期：2026-06-10

## 背景

本报告归档一次只读技术探针，用于判断当前 CLI 生成的 `CourseKnowledgeGraph` 是否真正被课程正文内容支撑，而不是只复刻 PDF 目录。

本轮不修改业务代码、不修改 OpenAPI、不新增前端入口、不引入 mock。所有运行结果来自真实 MySQL、Qdrant 和 embedding provider。

## 样本

- catalog_id：`b2444963f0e54587`
- course_id：`6c698badb60a4809`
- 课程：`C语言`
- Qdrant course_id：`b2444963f0e54587`
- SQL KG course_id：`6c698badb60a4809`

当前 CLI 生成 KG：

- 节点数：`116`
- 边数：`115`
- 生成方式：`../backend/tools/generate_knowledge_graph.py` 从外部大纲 / 目录文本生成 `nodes` / `edges` 并 upsert `course_knowledge_graphs`

## 已核实代码事实

- KG CLI 只读取 `--file` 或 `--outline`，不会自动从 CourseCatalog 资料中生成正式大纲。
- KG CLI 调 LLM 后只做结构校验：节点需有 `id/name/chapter`，边需引用已存在节点。
- KG CLI 直接 upsert `course_knowledge_graphs`，当前表是每课程唯一记录，缺版本和回滚能力。
- LearningPath 节点资源挂载依赖精确相等：
  - `Resource.knowledge_point == node_name`
  - `Resource.chapter == KG.chapter`
- Agent Service 不生成 SQL KG，只消费 Backend 传入的 `knowledge_graph` 生成 LearningPath。

## 探针 1：KG 节点到资源挂载

输出文件：

- `/tmp/kg-resource-probe/c-language-after-kg.csv`

结果：

- 20 个核心 KG 节点样本的 `candidate_count` 全部为 `0`。
- 当前班级资源共 4 个，全部为：
  - `chapter=课程整体`
  - `knowledge_point=综合知识点`

结论：

- 资源挂载失败不是排序问题，也不是 top-k 问题。
- 当前资源标签粒度和 KG 节点命名体系不一致，精确匹配无法挂载。
- 在 KG 未证明可靠前，暂停“资源生成继承 KG 节点名”落地，避免把未验证节点名固化为资源标签。

## 探针 2：KG 节点到 Qdrant chunk 初筛

运行目的：

- 先看 116 个 KG 节点是否能在 665 个 Qdrant chunk 中找到相关内容。

结果摘要：

- `kg_node_count=116`
- `qdrant_chunk_count=665`
- `top1_score_median=0.7348`
- `top1_score_avg=0.7427`
- `nodes_with_exact_name_in_top5=99/116 = 85.3%`

进一步检查发现：

- `top1_toc_like_count=112/116 = 96.6%`

结论：

- KG 节点大多能命中资料，但 top1 命中基本是目录页 / 索引页。
- 仅凭初筛不能证明 KG 有正文支撑。

## 探针 3：排除目录后的正文支撑对账

输出文件：

- `/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language.json`
- `/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language.csv`

跑前固定判据：

- 排除目录型 chunk 后，每个 KG 节点只在正文 chunk 池中取最高相似度。
- 若 `body_top1_score >= 0.70` 的节点占比 `>= 70%`，判定 `KG 有内容支撑，可继续`。
- 否则判定 `KG 主要是目录复刻，需改生成方式`。

结果：

- `kg_node_count=116`
- `total_qdrant_chunks=665`
- `excluded_toc_like_chunks=52`
- `body_chunk_count=613`
- `pass_count=25`
- `pass_ratio=21.6%`
- `body_top1_score_median=0.668`
- 决策：`toc_replica_needs_generation_rework`

结论：

- 当前 KG 不合格。
- 它不是完全凭空生成，但主要复刻目录结构，不能证明大多数节点有正文支撑。
- 不应推进 KG ready gate、审核 / 签字流程、LearningPath refresh UI 或资源继承 KG 节点名。

## 探针 4：正文 chunk 密度确认

输出文件：

- `/tmp/kg-resource-probe/body-chunk-density-c-language.json`

跑前固定判据：

- 剔除目录型 chunk 后，知识型正文 chunk 占比 `>= 60%`。
- 第 1-8 章每章至少有 `5` 个知识型正文 chunk。
- 满足则判定资料足够支撑路线 A 返工。

知识型正文标签：

- `explanatory_body`
- `code_example_explanation`
- `light_explanatory`

结果：

- `total_chunks=665`
- `toc_like_excluded=52`
- `body_chunks=613`
- `knowledge_like_count=465`
- `knowledge_like_ratio=75.9%`
- 第 1-8 章知识型覆盖：
  - 第1章：`48`
  - 第2章：`29`
  - 第3章：`26`
  - 第4章：`40`
  - 第5章：`50`
  - 第6章：`27`
  - 第7章：`32`
  - 第8章：`26`
- 决策：`materials_dense_enough_for_route_a`

结论：

- 资料本身够厚，不需要先补资料。
- KG 不合格的根因是生成方式没有读正文，而不是课程资料稀疏。

## 当前决策

暂停：

- KG ready gate 设计。
- 审核 / 签字流程设计。
- LearningPath refresh UI 接入。
- 资源生成继承 KG 节点名落地。

立即下一步：

1. 增加 KG 版本 / 回滚能力。
   - 当前 `course_knowledge_graphs` 是 upsert 覆盖唯一记录。
   - 后续会反复试验目录版、路线 A、可能的路线 B；没有版本会丢失对比基础。
   - 版本 / 回滚是返工实验基础设施，不是审核流程。

2. 按路线 A 返工 KG 生成。
   - 目录给骨架。
   - 正文 chunk 验证节点。
   - 正文 chunk 补充目录未覆盖但资料中真实存在的知识点。
   - 将正文对账探针变成生成时质检关卡。

3. 新 KG 生成后重跑两个探针。
   - KG-to-body chunk 正文支撑对账。
   - KG-Resource 对齐探针。

只有新 KG 通过正文支撑和资源对齐后，才继续讨论资源标签继承、审核 / 签字和 KG ready gate。

## 版本 / 回滚建议边界

版本 / 回滚可作为下一步开发任务单独推进，但应保持窄边界：

- 不改变 LearningPath 现有读取行为，默认仍读取当前 active KG。
- 增加历史版本保存和切换 / 回滚能力。
- 为每个版本记录生成来源、生成策略、摘要指标和创建时间。
- 不在本任务中加入人工审核流。

## 剩余风险

- 本轮内容密度分类是启发式规则，不等同人工语义标注。
- Qdrant chunk 本身来自 PDF 切片，部分 chunk 可能跨章节或包含索引 / 附录内容。
- 当前 KG-to-body 判据只用于决策返工方向，不是最终上线标准。
