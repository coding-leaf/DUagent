# Route A 可用正文支撑阈值设计

日期：2026-06-11

## 背景

Route A 第一版按 `body_top1_score >= 0.70` 裁剪 KG 后，真实 C 语言样本只保留 `22/116 = 18.97%` 节点，图结构碎片化。

随后已完成两类探针修正：

- Agent Service grounding 过滤补强：目录、索引、点线页码、附录目录、英文索引页码串等噪声被过滤。
- query 扩展：同时检索 `node.name` 与 `chapter + node_name + 相邻节点名`，取最高正文候选。

最新真实复验文件：

- KG：`/tmp/kg-resource-probe/c-language-active-kg-v1.json`
- Grounding：`/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json`

最新分布：

| 分数段 | 节点数 | 含义 |
| --- | ---: | --- |
| `>=0.70` | 57 | strong |
| `0.65-0.70` | 34 | good |
| `0.60-0.65` | 17 | weak_but_usable |
| `<0.60` | 7 | unsupported |
| 无候选 | 1 | unsupported |

按旧 `0.70` 单线判断仍只有 `57/116 = 49.14%`，但按 `0.60` 可用支撑线判断为 `108/116 = 93.10%`。

结论：`0.70` 对当前中文 OCR 教材 chunk 和 embedding 分数偏严；Route A 第一版不应继续按单一 `0.70` 裁剪。应改为“`>=0.60` 可进入 active KG，但 metrics 保留 strong/good/weak/unsupported 分布”。

## 范围

本轮要做：

1. Backend Route A 裁剪默认可用阈值从 `0.70` 调整为 `0.60`。
2. `filter_supported_knowledge_graph()` 增加正文支撑分档统计。
3. CLI 生成新 KG 版本时使用 `generation_strategy=route_a_prune_usable_060`。
4. 用现有 v3 grounding 文件生成新的 active KG 版本并复验节点数、边数、metrics。

本轮不做：

- 不修改 Agent Service grounding JSON 输出结构。
- 不改 Client API / Agent HTTP API / OpenAPI。
- 不做正文补点 / 正文聚类。
- 不做 KG ready gate。
- 不做 LearningPath refresh UI。
- 不修改 Qdrant 数据或上传文件。

## 支撑分档口径

节点支撑分档：

| band | 条件 | 处理 |
| --- | --- | --- |
| `strong` | `body_top1_score >= 0.70` | 保留 |
| `good` | `0.65 <= body_top1_score < 0.70` | 保留 |
| `weak_but_usable` | `0.60 <= body_top1_score < 0.65` | 保留，但在 metrics 中显式标记 |
| `unsupported` | `<0.60` 或无候选 | 裁剪 |

Route A active KG 保留条件：

```text
body_top1_score >= 0.60
```

`weak_but_usable` 可以进入 active KG，但不得在 metrics 或后续 ready gate 中被当成 strong 支撑。

## Metrics 设计

保留现有兼容字段：

- `body_top1_threshold`
- `candidate_node_count`
- `kept_node_count`
- `pruned_node_count`
- `body_support_pass_ratio`
- `pruned_nodes`

新增字段：

- `usable_support_threshold`: `0.60`
- `good_support_threshold`: `0.65`
- `strong_support_threshold`: `0.70`
- `strong_node_count`
- `good_node_count`
- `weak_but_usable_node_count`
- `unsupported_node_count`
- `usable_support_ratio`
- `strong_support_ratio`
- `good_or_strong_support_ratio`
- `support_band_counts`

示例：

```json
{
  "body_top1_threshold": 0.6,
  "usable_support_threshold": 0.6,
  "good_support_threshold": 0.65,
  "strong_support_threshold": 0.7,
  "candidate_node_count": 116,
  "kept_node_count": 108,
  "pruned_node_count": 8,
  "body_support_pass_ratio": 0.9310344827586207,
  "usable_support_ratio": 0.9310344827586207,
  "strong_support_ratio": 0.49137931034482757,
  "good_or_strong_support_ratio": 0.7844827586206896,
  "support_band_counts": {
    "strong": 57,
    "good": 34,
    "weak_but_usable": 17,
    "unsupported": 8
  }
}
```

## CLI 行为

`tools/generate_knowledge_graph.py` 当前已有 `--grounding-threshold`。

调整后：

- 默认 `--grounding-threshold` 改为 `0.60`。
- 当使用 `--grounding-file` 且阈值为 `0.60` 时，`generation_strategy` 写为 `route_a_prune_usable_060`。
- 如显式传入其他阈值，仍按传入阈值裁剪，`generation_strategy` 保持 `route_a_prune_unsupported`，避免本轮引入额外命名分支。

建议真实生成命令：

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 \
../.venv/bin/python tools/generate_knowledge_graph.py \
  --course-id 6c698badb60a4809 \
  --kg-json /tmp/kg-resource-probe/c-language-active-kg-v1.json \
  --grounding-file /tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json \
  --grounding-threshold 0.60
```

实际数据库 URL 以当前开发库为准，命令不得使用 SQLite。

## 成功判据

实现层：

- Unit tests 覆盖 `0.60/0.65/0.70` 分档。
- Existing `0.70` 行为可通过显式 threshold 保持。
- CLI pruning test 覆盖 weak node 被保留、unsupported node 被裁剪。

真实样本：

- 新版本 KG 节点数应接近 `108/116`。
- 新版本 KG 边数应显著高于旧 Route A `22 nodes / 2 edges`，不再是碎片图。
- `metrics.support_band_counts` 与 v3 grounding 分布一致：strong `57`、good `34`、weak `17`、unsupported `8`。
- 新版本 active，旧版本保留且可回滚。

## 后续决策门

如果 `route_a_prune_usable_060` 版本图结构通过：

1. 跑 KG-Resource 对齐探针。
2. 评估 LearningPath 读取 active KG 的结果。
3. 再设计 KG ready gate。

如果图结构仍不通过：

1. 不继续调低阈值。
2. 回到正文补点 / 正文聚类。
3. `generic_or_overbroad_node` 仍按拆分或删除处理。
