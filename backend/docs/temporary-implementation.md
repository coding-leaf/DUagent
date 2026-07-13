# Backend Temporary Implementation

## 当前已实现

- `profile/refresh`、`evaluation/refresh`、`learning-path/refresh` 已形成真实异步链路。
- `resources/generate` + webhook 已形成真实闭环。
- `tutoring/chat` 已形成 SSE 代理与消息落库链路。
- `quiz/generate`、`quiz/submit`、`quiz/result` 主链可用。

## 临时方案

### refresh 任务使用进程内 `asyncio.create_task`

- 当前行为
  - 返回 `202 + task_id` 后，由当前进程后台协程执行 Agent 调用和写库。
- 为什么是临时方案
  - worker reload、服务重启或 crash 后，任务无法恢复。
- 影响
  - 已创建的 `AsyncTask` 可能永久停留在 `processing`。

### learning-path 依赖 `CourseKnowledgeGraph`

- 当前行为
  - 接口本身可用，但课程若无 KG，则可能返回空 `nodes/edges`。
- 为什么是临时方案
  - KG 生产与导入能力尚未正式化。

### quiz diagnosis 语义仍在收口

- 当前行为
  - 功能主链可用，但 diagnosis 语义与个性化质量仍未完全统一。
- 为什么是临时方案
  - 仍需和前端、Agent 侧一起收口。

## 已知限制

- 当前模块文档刚完成拆分，旧 `WORKFLOW.md` 的部分解释性内容已迁出，但历史联调记录仍然存在。
- 根目录联调文档仍保留大量操作细节，短期内不会完全收敛到模块内文档。

## 替换条件

- 引入持久化 worker 或任务恢复机制后，可移除 refresh 的进程内协程临时说明。
- `CourseKnowledgeGraph` 数据准备链路正式化后，可移除 learning-path 的临时说明。

## 运维与开发工具级实现 (Non-production / Operations-level Designs)

当前系统打通了核心功能主链，但在新课程冷启动和非核心展示辅助能力上，依然依赖外部工具与运维级别脚本：

### 1. 📖 RAG 课程知识库的离线向量灌入 (`ingest_knowledge.py`)
- **实现行为**：课程资料由 Backend 上传后调用 `POST /agent/v2/knowledge/ingestions`，Agent Service v2 负责切片和写入 Qdrant；Workbench 通过注册的 RAG 工具检索这些切片。
- **限制**：后端无供教师上传教材并触发自动切片与 Embedding 向量化的 HTTP API / Web 界面。

### 2. 🔀 知识图谱智能提取与 upsert 命令行 (`generate_knowledge_graph.py`)
- **实现行为**：作为单课程过渡方案，图谱的 nodes 和 edges 的清洗去重与清洗由 `backend/tools/generate_knowledge_graph.py` 这个本地开发运维 CLI 工具一次性处理并 upsert 进数据库。
- **限制**：未提供产品化的 KG 在线编辑与大纲自动上传落库 UI。

### 3. 🛡️ 进程重启时异步任务的止血恢复 (`lifespan hook`)
- **实现行为**：FastAPI `lifespan` 挂载了 `_recover_orphaned_refresh_tasks()` 方法。当服务重启时，会将数据库中仍处于 `processing` 的历史长任务强制重置为 `failed`（状态标记为“服务重启，后台任务丢失”）。
- **限制**：这仅是针对单进程运行时的止血补偿手段，而非分布式工作流引擎的持久化断点续传。

### 4. 🧠 用户长期记忆 (Memory) 的离线压缩
- **实现行为**：长期记忆压缩和事实整理主要由 Agent 侧定时机制或触发规则驱动。
- **限制**：后端及前端没有提供可管理已被 AI 存储事实的交互面板。

---

## 联调负面评价与测试缺陷 (Test Suite Limitations & Negative Feedback)

虽然本次实战模拟全链路成功跑通，但在测试方案的健壮度与全面性上存在以下不足：

1. **测试运行遗留“脏数据”污染**：
   - 全链路模拟 `simulate_real_study.py` 在运行后没有 `TearDown` 自动清理数据机制，频繁运行会在本地 MySQL 数据库中留下随机后缀的僵尸学生、僵尸教师和无用课程数据。
2. **测试脚本的运行状态强依赖外部删除**：
   - 冒烟测试 `test_api.py` 的再次运行强制依赖在启动前执行 `rm -f test_v3.db`（或清除本地数据库），否则第二次运行时必将由于 UNIQUE 注册码约束发生严重冲突并崩溃。
3. **负面异常路径覆盖严重不足**：
   - `simulate_real_study.py` 仅覆盖了“快乐路径”（Happy Path）。对于诸如“Token 伪造”、“Header 校验失败”、“LLM 服务偶发超时”、“网络断连”等高风险的负面异常分支，在模拟测试中均无自动断言和用例覆盖。
4. **缺乏时延与性能性能指标硬性 Assert**：
   - 对异步任务状态采用简单的循环死等（`await asyncio.sleep(1.5)`）。测试断言仅关注“结果是否最终正确”，没有对“LLM 交互必须在指定时间内响应”等 P99 时延标准做任何度量或断言限制。
5. **契约校验较为脆弱**：
   - 历史上在测试脚本中曾出现读取 `q['stem']` 和 `res['url']` 导致 `KeyError` 挂掉的情况，这暴露出测试断言与 OpenAPI 契约之间缺乏静态强制约束绑定，完全依赖手工对齐，极易因后续开发漂移。
