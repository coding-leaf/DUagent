# Frontend Workflow

`WORKFLOW.md` 是施工日记和最近验证记录，不再承担功能主线判断职责。

阅读分工：

- 功能主线、状态和下一步：`docs/feature-ledger.md`
- 项目方向、结构和断层恢复：`docs/project-direction.md`
- 页面/API/Backend/Agent/测试证据：`docs/project-coverage-audit.md`
- 单次施工记录和最近验证：`WORKFLOW.md`

## 当前施工状态

- 当前主线以 `docs/feature-ledger.md` 为准。
- 当前最高优先级：KG 生成方式返工前置收口；先做 KG 版本 / 回滚基础设施，再按“目录骨架 + 正文 chunk 验证 / 补充”的路线 A 返工 KG 生成。
- 已确认可操作能力：Admin 课程资源库创建、资料上传、触发入库向量化、任务轮询、知识库状态展示、按资源库触发学习资源生成、生成资源列表、资料/资源软删除。
- 当前前端契约作废 / 不接入能力：资源生成 `/resources/generate`、Quiz 生成 `/quiz/generate`；教师端不提供生成资源入口，练习页不提供触发生题入口。
- 当前待设计阻塞点：KG 版本 / 回滚、正文支撑型 KG 生成；LearningPath / KG ready gate 后置，不能在 KG 可靠性和资源对齐未通过前推进。
- 当前工作区注意：`AGENTS.md` 已更新为新文档分工入口；未跟踪文件和存储产物不要混入提交。

## 最近验证

- 2026-06-11：Route A 可用阈值版 KG-Resource 对齐探针复验：
  - 重新盘点 `/tmp/kg-resource-probe/inventory-after-route-a-usable.json`：C 语言 catalog `b2444963f0e54587` / course `6c698badb60a4809` 已具备正式探针条件，`chunk_count=665`、`kg_node_count=108`、`resource_count=4`、`eligible_for_formal_probe=true`。
  - 导出正式探针 `/tmp/kg-resource-probe/c-language-route-a-usable-kg-resource-probe.csv`，共 `108` 行，全部来自 active KG。
  - 探针结果：`candidate_count=0` 的节点 `108/108`，即新版 KG 节点虽然正文支撑明显改善，但当前资源挂载规则仍无法命中任何资源或题目。
  - 只读核验资源元数据：当前 4 个课程资源全部为 `chapter=课程整体`、`knowledge_point=综合知识点`，而 KG 节点是具体章节/知识点；零命中原因是资源生成 metadata 粒度与 KG 节点体系不一致，不是 KG active 版本未生效。
  - 验证：`DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4 ../.venv/bin/python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory-after-route-a-usable.json` 通过；同库 `probe --catalog-id b2444963f0e54587 --course-id 6c698badb60a4809 --sample-mode all --format csv` 通过。
  - 附注：`../.venv/bin/python -m pytest tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider` 在当前工具会话中无结果输出，但进程表确认无 pytest 子进程残留；本次结论基于只读 MySQL probe 命令和导出 CSV。
- 2026-06-11：Route A 可用正文支撑阈值实现并生成新 active KG：
  - Backend Route A 裁剪默认线从强支撑 `0.70` 调整为可用支撑 `0.60`，并保留 `strong/good/weak_but_usable/unsupported` 分档 metrics。
  - `body_support_pass_ratio` 继续按传入阈值计算；`usable_support_ratio` 固定按 `0.60` 计算，避免后续 ready gate 把 weak support 当作 strong support。
  - CLI `--grounding-threshold` 默认改为 `0.60`；默认 Route A 版本写入 `generation_strategy=route_a_prune_usable_060`，显式非 `0.60` 阈值仍写 `route_a_prune_unsupported`。
  - 真实 C 语言样本已在开发库 `duagent` 生成新 active KG：`graph_id=27c3acb1e98a49d1`，`version=3`，`108` nodes / `100` edges，明显高于旧 Route A `22` nodes / `2` edges。
  - metrics 核验：`candidate_node_count=116`、`kept_node_count=108`、`pruned_node_count=8`、`body_support_pass_ratio=0.9310344827586208`、`support_band_counts={strong:57, good:34, weak_but_usable:17, unsupported:8}`。
  - `pruned_nodes` 详细列表暂保留，未来大图需要做限长或外部诊断产物。
  - 验证：Backend `../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q -p no:cacheprovider` 19/19 passed；MySQL versioning 回归 8/8 passed；真实生成命令成功。
- 2026-06-11：KG residual TOC/index 过滤漏网小补丁完成：
  - 按补点决策文件中的 `filter_review_first` 结论，增强 Agent Service KG grounding 过滤，新增英文索引页码串、单行稀疏点线页码、`索引/目录 + 点线/页码` 噪声识别。
  - TDD 覆盖：`expression ...，52，200` 这类英文索引、`...30 1.5.1 文件复制 ...31` 单行点线目录、`252 索引 ...` 尾部索引残留均会 fallback 到下一个正文候选。
  - 真实 C 语言样本复验：`/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json`；原 7 个 `residual_toc_or_index_noise` 节点均换成非索引候选，但整体 `>=0.70` 仍为 `57/116=49.14%`，说明过滤漏网已清理，下一步仍需正文补点/聚类。
  - 验证：Agent `./.venv/bin/pytest tests/test_kg_body_grounding.py tests/test_kg_body_grounding_tool.py tests/test_vector_store.py -q` 20/20 passed。
- 2026-06-10：KG 正文候选过滤 + query 扩展探针完成：
  - Agent Service `memory/kg_body_grounding.py` 增强目录/索引噪声过滤，新增点线页码目录、附录目录/索引识别；`tools/kg_body_grounding.py` 新增可选 `--query-expansion`，默认行为不变。
  - query 扩展策略不是替换单节点名，而是同时检索 `node.name` 和 `chapter + node_name + 相邻节点名`，取最高正文候选，避免已支持节点回退。
  - 真实 C 语言样本复验：baseline `22/116=18.97%`；仅过滤后 `18/116=15.52%`（纠正目录误判但不提分）；过滤 + query 扩展取最优后 `57/116=49.14%`，baseline `0.65-0.70` 的 49 个边缘节点有 23 个过线，且无已支持节点回退。
  - 结论：第 1、2 步有效但仍未达到固定成功线 `>=70%`；下一步应进入正文补点 / 正文聚类策略设计，不继续调阈值。
  - 验证：Agent `./.venv/bin/pytest tests/test_kg_body_grounding.py tests/test_kg_body_grounding_tool.py tests/test_vector_store.py -q` 19/19 passed；真实探针输出 `/tmp/kg-resource-probe/c-language-route-a-grounding-filtered.json`、`/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best.json`。
- 2026-06-10：Route A no-go 归因完成：
  - 已分析 `/tmp/kg-resource-probe/c-language-route-a-grounding.json` 的 116 个节点 grounding 结果。
  - 分数分布：`>=0.70` 22 个；`0.65-0.70` 49 个；`0.60-0.65` 33 个；`<0.60` 12 个；无候选 0 个。
  - 启发式归类：`toc_or_index_noise` 47 个、`near_threshold_body_match` 21 个、`low_score_body_match` 17 个、`near_threshold_unclear` 6 个、`low_score_or_wrong_candidate` 3 个、`supported` 22 个。
  - 结论：no-go 不是资料缺失，主要是目录/索引噪声仍进入候选、单节点名 query 太弱、目录候选直接裁剪会把 KG 变成碎片图。下一步先加强正文候选过滤和 query 扩展探针，再决定是否做正文补点 / 正文驱动候选生成。
  - 归档报告：`docs/superpowers/specs/2026-06-10-route-a-no-go-attribution-report.md`。
- 2026-06-10：Route A 真实 C 语言样本闭环验收：
  - 已对开发库 `duagent` 执行已提交迁移 `backend/migrations/2026-06-10-version-course-knowledge-graphs.sql`，旧目录版 KG 成为 `version=1,is_active=1`，`116` nodes / `115` edges。
  - 从 active KG 导出 `/tmp/kg-resource-probe/c-language-active-kg-v1.json`，用 Agent CLI 真实检索 Qdrant catalog `b2444963f0e54587`，输出 `/tmp/kg-resource-probe/c-language-route-a-grounding.json`。
  - Grounding 结果：`116` 节点中 `body_top1_score>=0.70` 的节点 `22` 个，占比 `18.97%`，median `0.6618`，未达到跑前固定成功线 `>=70%`。
  - Backend CLI 用 `--kg-json /tmp/kg-resource-probe/c-language-active-kg-v1.json --grounding-file /tmp/kg-resource-probe/c-language-route-a-grounding.json` 创建 Route A 新 KG：`graph_id=1801d8e677d04a43`，`version=2,is_active=1`，`source_type=route_a_body_grounded`，`generation_strategy=route_a_prune_unsupported`，`22` nodes / `2` edges，parent 指向旧 `f36b0d8580724805`。
  - 数据库只读核验：version 1 已 inactive，version 2 active，`metrics.body_support_pass_ratio=0.1896551724137931`、`kept_node_count=22`、`pruned_node_count=94`。
  - 结论：Route A 第一版“只裁剪无支撑节点”工具链可跑通，但真实样本验收 **no-go**；KG 生成还不能算完成。下一步不是测试收尾，而是改生成策略：分析被裁剪节点和正文覆盖，推进正文补点 / 更稳的正文驱动候选生成。
  - 额外修复：`backend/tools/generate_knowledge_graph.py` 增加 `--kg-json`，避免真实闭环重新调 LLM 导致 grounding 节点 id 不匹配；CLI 结束时显式 `engine.dispose()`，收口 aiomysql event loop closed 噪声。
  - 验证：Backend `../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q` 15/15 passed；Backend MySQL `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider` 8/8 passed。
- 2026-06-10：KG 版本化与 Route A 工具链阶段性接入：
  - 已完成 KG 版本 / 回滚基础设施：`course_knowledge_graphs` 支持 `version/is_active/source_type/generation_strategy/metrics/parent_graph_id`，LearningPath 默认读取 active KG，`generate_knowledge_graph.py` / `import_knowledge_graph.py` 不再覆盖旧 KG，而是创建版本或切换 active。
  - 已完成 Agent 侧只读正文支撑 scorer：`agent_service/memory/kg_body_grounding.py` 对 KG 节点逐个 embedding，检索 Qdrant `course_knowledge`，过滤目录型 chunk，输出 `body_top1_score/chunk_id/source_file/preview/supported`。
  - 已完成两段式 Route A 工具链：Agent CLI `agent_service/tools/kg_body_grounding.py` 导出 grounding JSON；Backend CLI `backend/tools/generate_knowledge_graph.py --grounding-file ...` 读取该 JSON，调用纯裁剪层保留正文支撑节点、裁掉悬空边，并写入 `route_a_body_grounded / route_a_prune_unsupported` 新版本。
  - 架构边界：Backend 不导入 Agent Service、不直接访问 Qdrant；Agent Service 不读写 Backend SQL；本阶段未新增 Client API / Agent HTTP API。
  - 已运行：Agent `./.venv/bin/pytest tests/test_kg_body_grounding.py tests/test_kg_body_grounding_tool.py tests/test_vector_store.py -q` 14/14 passed；Backend `../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q` 13/13 passed；Backend MySQL `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider` 8/8 passed。
  - Commits：`705ae8f 增加KG版本化表结构`、`b89449e 增加KG版本切换服务`、`c1d2575 切换KG读取为active版本`、`5404b5e 改造KG导入工具保留版本`、`33599f4 增加KG正文支撑裁剪逻辑`、`a90cac6 新增KG正文支撑度评分模块`、`0bec53e 新增KG正文支撑导出工具`。Backend Route A CLI 接入提交见本轮后续 commit。
  - 未完成：尚未对真实 C 语言 `116` 节点样本生成 Route A 新版本，也尚未重跑成功线验收；固定成功线仍是排除目录型 chunk 后 `body_top1_score>=0.70` 节点占比从 `21.6%` 提升到 `>=70%`。
- 2026-06-10：KG 生成方式真实探针与返工方向确认：
  - 真实运行现有 CLI `../backend/tools/generate_knowledge_graph.py`，对 catalog `b2444963f0e54587` 绑定教学班 `6c698badb60a4809` 生成 SQL KG：`116` 个节点、`115` 条边。该 CLI 只从外部 `--file/--outline` 大纲文本生成 KG，未自动读取 CourseCatalog 正文 chunk。
  - 资源挂载探针：`/tmp/kg-resource-probe/c-language-after-kg.csv`。20 个核心 KG 节点样本 `candidate_count=0`；当前课程 4 个资源全部是 `chapter=课程整体`、`knowledge_point=综合知识点`，与 KG 具体节点名 / 章节不在同一命名体系。
  - KG 初筛对账：116 个 KG 节点检索 665 个 Qdrant chunks，`nodes_with_exact_name_in_top5=99/116=85.3%`，但 `top1_toc_like_count=112/116=96.6%`，说明表面命中主要来自 PDF 目录 / 索引。
  - 正文支撑对账：`/tmp/kg-resource-probe/kg-to-body-chunk-probe-c-language.json`、`.csv`。跑前固定判据为“排除目录型 chunk 后，`body_top1_score>=0.70` 的节点占比 `>=70%` 才算 KG 有内容支撑”；实际 `25/116=21.6%`，`body_top1_score_median=0.668`，决策为 `toc_replica_needs_generation_rework`。
  - 正文 chunk 密度确认：`/tmp/kg-resource-probe/body-chunk-density-c-language.json`。剔除 52 个目录型 chunk 后，正文 chunk `613` 个，知识型正文 `465/613=75.9%`；第 1-8 章知识型覆盖分别为 `48/29/26/40/50/27/32/26`，决策为 `materials_dense_enough_for_route_a`。
  - 结论：资料本身够厚，不需要先补资料；当前 KG 不合格的根因是生成方式主要复刻目录、没有正文验证。暂停 KG ready gate、审核 / 签字流程、LearningPath refresh UI、资源继承 KG 节点名落地。
  - 下一步顺序：先做 KG 版本 / 回滚基础设施；再按路线 A 返工 KG 生成（目录给骨架，正文 chunk 验证节点并补充正文中真实存在的知识点）；新 KG 生成后重跑正文支撑对账和 KG-Resource 对齐探针。
  - 归档报告：`docs/superpowers/specs/2026-06-10-kg-body-grounding-probe-report.md`。
- 2026-06-10：KG-Resource 对齐探针真实盘点与校准执行：
  - 已新增只读 KG-Resource 对齐探针 service/CLI，用于盘点 catalog/course 数据、导出 KG/LearningPath 节点候选、汇总人工标注；未新增 API route，未修改前端页面，未修改 OpenAPI。
  - 当前服务状态：Backend `8001`、Agent Service `8002`、Frontend `5173` 均返回 200；MySQL、Qdrant 容器在线。探针 CLI 本身只读 MySQL，不调用 Agent Service。
  - 数据底盘盘点输出：`/tmp/kg-resource-probe/inventory.json`，共 10 个 catalog/course 组合。
  - `89f51dfbdedc4995` 盘点结果：course `59360ad8b8f445b7`，`chunk_count=1`，`kg_node_count=0`，`learning_path_node_count=0`，`resource_count=1`，`quiz_count=0`，`eligible_for_formal_probe=false`。
  - 已对 `89f51dfbdedc4995` 执行 calibration 导出：`/tmp/kg-resource-probe/89f51-calibration.csv`；导出命令成功，必需列完整，节点行数为 0。该 catalog 当前只能证明探针流程和表头可跑，不能产出命中率或 go/no-go。
  - 正式第二 catalog 选择结果：当前 inventory 中 `eligible_for_formal_probe=true` 的第二 catalog 数量为 0；因此本轮不能输出 KG-Resource 对齐 go/no-go。
  - 上线前置条件：补充或构造足量真实样本，要求 KG/LearningPath 节点可抽取 10-15 个核心节点，且资源或题目存在可匹配的 `knowledge_point` 或 `chapter` 元数据。
  - CLI 运行态修复：真实 MySQL inventory 首次暴露 `aiomysql RuntimeError: Event loop is closed` 退出噪声，已在 CLI 结束时显式 `engine.dispose()`，重跑 inventory 不再出现该警告。
  - 已运行：
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_probe_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider`：13/13 passed。
    - `../.venv/bin/python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory.json`：通过。
    - `../.venv/bin/python tools/probe_kg_resource_alignment.py probe --catalog-id 89f51dfbdedc4995 --calibration --sample-mode all --format csv --out /tmp/kg-resource-probe/89f51-calibration.csv`：通过，`wrote 0 calibration probe rows`。
    - `../.venv/bin/python` 校验 `/tmp/kg-resource-probe/89f51-calibration.csv` 必需列：`missing=[]`，`row_count=0`。
    - `../.venv/bin/python` 检查 `/tmp/kg-resource-probe/inventory.json` 正式样本候选：`eligible_count=0`。
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/node_resources_probe_regression?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_node_resources.py -q -p no:cacheprovider`：1/1 passed；测试初始化补充 `engine.dispose()` 以适配 MySQL async engine。
  - Commits：`58dec7e 新增KG资源对齐探针服务`、`361b3a7 新增KG资源对齐探针命令行工具`、`988c463 修复KG探针命令连接释放`。
- 2026-06-09：CourseCatalog 资源消费闭环前端落地完成：
  - 学生端 `Dashboard.jsx` 仅把“有课程但无资源”空态文案改为“课程资源正在准备中 / 请稍后查看”，`data-testid="resources-empty"` 保留不变，无课程空态仍是“暂无课程 / 请先加入一门课程”。
  - 教师端 `TeacherConsole.jsx` 新增只读“本班学习资源”区，按当前教学班 `course_id` 调 `GET /resources?course_id=...&page=1&page_size=50`，展示绑定资源库状态、资源卡片，并可跳转现有 `/resource/:id` 详情。
  - 教师端未恢复生成 / 上传 / 删除入口，仍不调用 deprecated `/resources/generate`。
  - E2E 回归通过：`npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy|Teacher console shows catalog-bound class resources|Teacher console shows no-resource fallback|Teacher console does not expose"` 通过 4/4。
  - 前端检查通过：`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - 契约检查：未修改 Backend / OpenAPI / `../docs/`，继续按班存、按班读，不引入 catalog-level resource API。
  - Commit：`998b29d 调整学生资源准备空态`、`e6421d9 新增教师只读资源面板`。
  - 剩余风险：`ResourceDetail.jsx` 仍无显式 404/403 错误态；教师资源区 E2E 存在重复路由设置，后续测试扩展时可再抽 helper。
- 2026-06-09：Admin CourseCatalog 入库 / 资源生成 / 教师绑定 / 学生消费真实多服务冒烟验收通过：
  - 真实服务：Backend `8001`、Agent Service `8002`、MySQL、Qdrant 均在线；Agent health 返回 `qdrant_connected=true`、`model_loaded=true`。
  - 首次 live smoke 暴露运行态配置问题：Agent Service 未带共享上传目录，入库 task `b09513e51aef4431` 失败，错误为 `material does not exist`。根因是 Backend 文件在 `../backend/storage/course_catalogs`，Agent 默认从自身 `storage/course_catalogs` 解析。重启 Agent 时显式设置 `COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs` 后通过。
  - 通过正式 Client API 创建 Admin/Teacher/Student，创建资源库 `89f51dfbdedc4995`，上传真实 md 资料 `2ff62f2a34134655`，触发入库 task `d0b234d74df94822`，任务 `completed`，资源库 `status=ready`、`knowledge_status=ready`、`chunk_count=1`。
  - 教师可见 ready CourseCatalog，并绑定创建教学班 `59360ad8b8f445b7`，确认 `CourseOffering.id == Course.id`。
  - Admin 触发资源库级资源生成 task `39dfbd5feb9a4cb7`，任务 `completed`，fan-out 到课程 `59360ad8b8f445b7`，生成资源 `c9faf2f4ce304d3d`（document）和 `2ca8a6af636f4b20`（mindmap）。
  - 学生加入教学班后，`GET /resources` 可见生成资源，`GET /resources/{id}` 可打开真实内容；软删除 `2ca8a6af636f4b20` 后 Admin/Student 列表均隐藏，数据库只读核验该资源 `is_deleted=1`，未软删 document 仍保留。
  - Qdrant 只读核验：按 `course_id=89f51dfbdedc4995` 过滤 `course_knowledge_v1_1024` count 为 1。
  - 回归验证：`../.venv/bin/pytest tests/test_admin_catalog_resource_generation.py tests/test_course_catalog_ingestion.py tests/test_resources_async.py tests/test_course_catalog_ready_gate.py -q` 通过 54/54；`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"` 通过 2/2；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过。
- 2026-06-09：Admin 课程资源库资源生成和软删除前端接入完成：
  - `CourseCatalogDrawer.jsx` 新增 Admin-only 生成学习资源表单、生成任务独立轮询、生成资源列表、资料软删除和生成资源软删除。
  - 前端只调用已写入 Client API 的 Admin 端点：`GET /admin/course-catalogs/{catalog_id}/resources`、`POST /admin/course-catalogs/{catalog_id}/resources/generations`、`DELETE /admin/resources/{resource_id}`、`DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}`。
  - 教师端保持无生成资源入口，不调用 deprecated `/resources/generate`。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"` 通过 2/2；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-09：纠正生成接口前端契约主线：
  - 将 `/resources/generate`、`/quiz/generate` 标记为当前前端契约作废 / 不接入，保留历史后端能力背景但不再作为教师端 UI 或下一步联调主线。
  - 当前主线回到 Admin 资源库创建、资料上传、触发入库 / 向量化、教师绑定 ready CourseCatalog 创建教学班，以及学生 / 教师如何消费入库后的资源和知识库内容。
  - 同步修正 `docs/feature-ledger.md`、`docs/project-direction.md`、`docs/project-coverage-audit.md`、Client API Markdown 与 OpenAPI 描述。
  - 验证：文档语义扫描、OpenAPI JSON 格式检查、`git diff --check`。
- 2026-06-09：重建功能进度主线看板：
  - 新增 `docs/feature-ledger.md`，按“用户实际能操作什么”重建开发进度账本。
  - 逐页核查真实前端调用，区分 `已可操作`、`后端闭环`、`联调待验收`、`前端无入口`、`待设计`、`暂缓`。
  - 确认资源生成和 Quiz 生成当前没有前端正式入口；Admin 资料上传和向量化已可操作。
  - 验证：占位符扫描无匹配；`git diff --check -- docs/feature-ledger.md` 通过。
  - Commit：`e7f1104 重建功能进度主线看板`。
- 2026-06-09：修正项目覆盖审计实际功能：
  - 修正 `docs/project-coverage-audit.md`，明确 Admin 界面已支持上传 `txt/md/pdf` 资料并触发 Agent 切片、embedding、Qdrant upsert，Backend 回写 `chunk_count/knowledge_status`，前端轮询刷新状态。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ingestion.py -q` 通过 22/22；`cd ../agent_service && ../.venv/bin/pytest tests/test_knowledge_ingestion_api.py -q` 通过 13/13；`cd ../agent_service && ../.venv/bin/pytest tests/test_ingest_knowledge.py tests/test_course_knowledge_store.py -q` 通过 11/11；`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 通过 1/1。
  - Commit：`4c6ccf7 修正项目覆盖审计实际功能`。
- 2026-06-08：Phase B 资源生成 / Quiz 生成前置 CourseCatalog ready gate 完成：
  - Backend 新增共享 ready gate：教学班 `course_id` 解析到 `CourseOffering.catalog_id`，`CourseCatalog.status=ready` 且 `knowledge_status=ready|partial` 且 `chunk_count>0` 才允许生成。
  - `/resources/generate` 和 `/quiz/generate` 共用同一套校验；Agent payload 使用 `CourseCatalog.id`，Backend 持久化仍使用教学班 id。
  - OpenAPI、接口规范和前端 orphan service 清理已同步。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q` 通过 20/20；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - Commits：`f6b8b19`、`04107e4`、`1f8d765`、`7cf6a36`、`9778020`。
- 2026-06-08：AIChat 历史消息对象知识点白屏修复：
  - `AIChat.jsx` 对历史消息、SSE `knowledge_points` 和 `suggestions` 做可展示文本归一化，避免对象直接进入 React child。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过 1/1；`npm run lint` 通过；`npm run build` 通过。
  - 契约注意：OpenAPI 仍声明 `messages[].knowledge_points[]` 为 string，真实历史响应出现对象元素；前端当前只做兼容防白屏。
- 2026-06-08：CourseCatalogDrawer 入库任务轮询与状态文案修复：
  - `/tasks/{task_id}` 查询异常不再被本地改写为任务失败，继续轮询并展示“任务状态查询失败，正在重试”。
  - 资源库、知识库、资料、上传队列和任务状态按设计展示中文标签。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 通过；`npm run lint` 通过；`npm run build` 通过。
- 2026-06-08：AdminConsole 课程资源库入库 UI 接入完成：
  - 新增资源库详情抽屉，支持资料列表、知识库状态、批量选择文件逐个上传、手动触发入库和 `GET /tasks/{task_id}` 轮询。
  - 上传请求使用 `FormData`，不直连 Agent Service，不使用 mock 数据补字段。
  - 验证：`npm run lint` 通过；`npm run build` 通过。
- 2026-06-08：Phase B1 CourseCatalog 资料入库后端编排完成：
  - Backend 新增 `POST /admin/course-catalogs/{catalog_id}/ingestions`，创建 `course_catalog_ingestion` AsyncTask，后台调用 Agent `/agent/v1/knowledge/ingestions`，并回写资料和资源库状态。
  - 验证：Agent `test_knowledge_ingestion_api.py` 通过 13/13；Backend `test_course_catalog_ingestion.py test_course_catalogs.py` 通过 23/23；OpenAPI JSON 校验通过。

## 历史摘要

- 阶段一真实 Backend 主链路已完成 E2E 验收：登录、注册、课程、资源列表、学习路径基础展示、Quiz、AI Chat、教师基础学情、管理员基础页面。
- 阶段二已完成多项契约收口：学生端数据契约审查、P0 假展示清理、ResourceDetail 内容、LearningPath 节点资源、教师端学生聚合、AdminConsole 既有契约对齐。
- CourseCatalog 主线已完成：三表、教学班绑定、Admin 创建资源库、Admin 上传资料、Agent 入库向量化、知识库状态展示、Admin 资源库资源生成、资料/资源软删除、历史资源/Quiz 生成前 ready gate。
- TeacherConsole 曾短暂接入资源生成 UI；CourseCatalog 主线调整后已移除。当前教师资源生成和 Quiz 生成在前端契约中作废 / 不接入，不是当前主线。
- 详细历史请回看 git 提交、`docs/superpowers/specs/`、`docs/superpowers/plans/` 和 `docs/project-coverage-audit.md`。

## 本地联调注意事项

- 浏览器前端如果使用真实 Backend，请优先使用 `http://localhost:5173`，避免 `127.0.0.1` 与 Backend CORS origin 不一致。
- 推荐启动方式：`VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev`。
- Admin CourseCatalog 入库和资源生成真实验收需要 Backend、Agent Service、MySQL、Qdrant/storage、embedding provider 配置同时可用。
- Agent Service 必须带共享上传目录运行：`COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs`。缺失时入库会失败为 `material does not exist`。

## 下一步指针

下一步队列不在本文件维护，统一查看 `docs/feature-ledger.md` 的“当前下一步队列”。
