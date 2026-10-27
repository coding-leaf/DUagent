# Technical Design: 基于 AgentScope 原生编排重构多智能体生成并修复数据库死锁

## 1. 架构总览 (Architecture Overview)

```
[前端界面 / Chat / API]
        │
        ▼ (POST /personalized-resources/generate)
[Backend FastAPI]
  - 创建 AsyncTask(status="processing", task_type="resource_generation")
  - 关联 UserPersonalizedResource(task_id=task_id)
  - 分发至 Agent Service: POST /agent/v2/personalized-resources/generations
        │
        ▼
[Agent Service - AgentScope 原生 TeamPipeline]
  ┌─────────────────────────────────────────────────────────┐
  │  Leader: PlanningLeaderAgent (AgentScope Agent)         │
  │  - 解析学习目标、学生画像与勾选的偏好                    │
  │  - 生成任务分派计划，通过 _TeamAssign 工具同时调用各成员 │
  └──────────────────────────┬──────────────────────────────┘
                             │ (AgentScope 框架底层 asyncio.gather 并发调度)
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
   [Lesson Member]    [Mindmap Member]    [Quiz Member]
   (AgentScope Agent) (AgentScope Agent)  (AgentScope Agent)
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │  AgentScope Toolkit (标准 FunctionTool 挂载)            │
  │  ├─ RAG 知识检索 (Qdrant 向量匹配切片)                   │
  │  ├─ 格式校验工具 (静态语法 / 题型字段校验)              │
  │  ├─ 草案暂存工具 (Backend /internal/.../drafts)         │
  │  └─ 发布入库工具 (Backend /internal/.../publish)         │
  │       * 防御截断: knowledge_point[:100], title[:200]    │
  └──────────────────────────┬──────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
      [成功完成]                        [任一环节异常]
  link_published_generation         统一触发任务失败闭环
  AsyncTask: status="completed"      AsyncTask: status="failed"
  UserPersonalizedResource 绑定      记录 error_message
```

---

## 2. 核心模块重构与详细设计

### 2.1 数据库死锁与数据契约防御
- **`backend/app/services/personalized_resource_generation_service.py`**:
  在 `publish` 函数中构建 `Resource` 实体时，增加安全长度截断：
  ```python
  raw_kp = str(draft.get("knowledge_point") or draft.get("chapter") or "综合")
  safe_kp = raw_kp.strip()[:100]  # 严格对齐 resources.knowledge_point varchar(100)
  safe_title = str(draft.get("title") or "个性化学习资料").strip()[:200]

  resource = Resource(
      course_id=generation.course_id,
      title=safe_title,
      type=generation.resource_type,
      description=str(draft.get("description") or ""),
      content=str(draft.get("content") or ""),
      chapter=str(draft.get("chapter") or "")[:100],
      knowledge_point=safe_kp,
      tags=draft.get("tags") or [],
      url="",
      create_by=generation.user_id,
  )
  ```
- **Backend 任务失败同步接口**:
  在 `backend/app/api/v1/internal_personalized_resources.py` 中新增或加固任务失败上报接口：
  `POST /internal/personalized-resources/tasks/{task_id}/fail`，当 Agent 生成异常退出时，可靠更新 `AsyncTask`：
  ```python
  task.status = "failed"
  task.error_code = error_code
  task.error_message = error_message[:500]
  task.completed_at = datetime.now(timezone.utc)
  ```

### 2.2 AgentScope 原生 `TeamPipeline` 编排重构
- **废弃手写轮子**:
  重构 `agent_service_v2/generators/personalized_resource_flow.py`，移除原有的手写单线程过程式 `for` 循环与手动重试胶水代码。
- **构建 Leader Agent**:
  使用 `AgentScope.agent.Agent`，系统 Prompt 配置为“教学主管”，挂载 `_TeamAssign` 工具，根据输入的 `goal` 与 `preferences` 分析任务，分派任务给各领域的专家 Member。
- **构建领域专长 Member Agents**:
  通过 `TeamMember` 封装专门的 Member Agent：
  - `lesson_worker`: 负责专业讲义/课件；
  - `diagram_worker`: 负责 Mermaid 概念思维导图；
  - `quiz_worker`: 负责多题型单选/多选题；
  - `reading_worker`: 负责拓展阅读；
  每个 Member 挂载对应的 AgentScope `FunctionTool`（RAG 工具、校验工具、入库工具）。
- **利用 AgentScope 并发机制**:
  `TeamPipeline` 原生将 Leader 在同一轮中调用的多个 `TeamAssign` 工具转化为后台并发 Task (`asyncio.create_task` + `asyncio.gather`)，多资源生成天然并行执行，耗时降低 50% 以上。
- **全局异常拦截与失败闭环**:
  在 Agent Service 的 Pipeline 外部包裹统一 `try...except` 块，无论是 LLM 超时、网络断开还是未知异常，必定在 `finally` 或 `except` 中向后端发送失败回调，彻底告别假死转圈。

### 2.3 前端与 SSE 事件流打通
- 将 `TeamPipeline.reply_stream` 中的框架原生事件（Leader 思考、Member 思考、工具调用）转换为 `EduEventType`，通过已有的 `EventStreamBroadcaster` 广播出去，前端工作区可接收到细粒度的实时进度更新。
- 前端轮询设置 180s 超时兜底熔断，当超过指定时间任务仍处于 `processing` 时，前端友好提示“生成时间较长或后台异常，已自动为您重置”，提供重试入口。

---

## 3. 兼容性与安全验证
- **向下兼容**: 保持现有 HTTP 请求与响应体结构一致，不破坏原有接口规范。
- **测试覆盖**:
  - 针对超长 `knowledge_point`（>100 字符）的写入测试；
  - 针对异常中断下 `async_tasks` 自动置为 `failed` 的单测；
  - 针对 `TeamPipeline` 并发生成多资源的单元测试；
  - 全仓 7 项 CI 门禁检查。
