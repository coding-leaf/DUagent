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
