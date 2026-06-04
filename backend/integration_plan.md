# Backend-Agent 联调与系统收口计划

> **状态：暂停执行，等待产品需求与 API 契约重新对齐**
>
> `2026-06-04` 最新口述产品方向已改变资源与题目生成方式：
>
> - 资源改为课程级公共资源，由 Agent 统一生成后供通过课程码加入课程的学生共享。
> - 题目改为课程级公共题库，由 Agent 统一生成；学生答题结果仍按个人记录。
> - 新增每日一题/多题作业与完成打卡、累计学习时长、本周最高正确率、认知成长曲线、知识点练习掌握度、教师端学生状态聚合等候选能力。
>
> 当前正式 Client API、Agent API、SQL 模型和前端静态页面尚未完成上述方向的统一设计。本文件下方原有任务只保留为历史分析，不应直接继续实施，尤其不得据此修改正式契约。

本计划基于当前 Backend 的代码现状、冒烟测试结果以及 `code_researcher` 的深入分析，旨在指导下一步如何收口系统级能力缺口。

---

## 0. 当前下一步：先完成五方差距矩阵

在继续开发前，需要按每个页面能力同时核对：

1. 产品需求语义和 MVP 范围
2. 前端静态页面实际展示字段
3. Client API 路径、参数和响应字段
4. Agent API 负责生成的结构化结果
5. Backend SQL 数据来源、聚合规则和权限边界

优先确认的能力：

- 课程公共资源生成与共享
- 课程公共题库生成与共享
- 每日作业发布、学生完成状态与打卡
- 页面学习时长累计
- 本周最高正确率
- 知识点练习掌握度
- 认知成长曲线
- 教师端学生状态聚合

在矩阵和契约变更草案确认前：

- 不新增 Client API 字段、路径、枚举或同步/异步语义。
- 不新增 Agent API 字段、任务类型或状态语义。
- 不按前端静态示例中的占位数据猜测 Backend 实现。
- 现有接口只作为已打通技术链路继续验证，不视为最终产品形态。

## 1. 当前联调与测试现状

* **冒烟测试 (`python tests/test_api.py`)**
  * **结果**：`56/56` 全量通过 (`ALL TESTS PASSED!`)。
  * **关键发现**：在以 `pytest` 跑全量测试时，部分以 `async def test():` 开头并由 `asyncio.run(test())` 独立执行的辅助测试脚本（如 `test_api.py`, `test_refresh_async.py`）会被 `pytest` 错误识别为标准测试用例，由于缺乏 `@pytest.mark.asyncio` 报错 `async def functions are not natively supported`。这说明它们不适合通过全局 `pytest` 运行，而应继续以 **`python tests/xxxx.py`** 的方式运行，或未来重构其函数名以防 `pytest` 误捕获。
* **Agent 状态**：Agent 本地服务状态健康且 Qdrant 向量数据库连接正常。

---

## 2. 三大核心能力缺口收口方案

经过对 `app/api/v1/teaching.py`、`app/api/v1/quiz.py` 和各 refresh 异步链的深度分析，我们规划了如下的实现细节：

### 任务 1: 消除学习看板占位数据 (`GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning`)
当前该端点返回数据中，`overall_score` 是硬编码的 `75.0`，且 `weak_points` 和 `recent_activity` 均为空数组。
* **具体做法**：
  1. **总体评分 (`overall_score`)**：
     从 `quiz_sessions` 表中计算该学生在此课程下的所有已完成练习的平均分：
     ```python
     avg_score_query = select(func.avg(QuizSession.score)).where(
         QuizSession.user_id == student_id,
         QuizSession.course_id == class_id,
         QuizSession.is_deleted == False
     )
     overall_score = (await db.execute(avg_score_query)).scalar() or 0.0
     ```
  2. **薄弱知识点 (`weak_points`)**：
     提取 `UserProfile.knowledge_coordinates` 中所有 `status == "learning"` 状态的知识点，以及 `cognitive_blindspots` 级别为中/高（Medium/High）的知识点。
  3. **最近动态时间线 (`recent_activity`)**：
     查询该学生该课程下最近 5 条动态（合并排序）：
     * **练习**：`QuizSession` 提交记录。标题：`"完成章节 '{q.chapter}' 练习，正确率 {q.score}%"`，类型：`"quiz"`。
     * **提问**：`Conversation` 创建。标题：`"参与智能辅导: {c.title}"`，类型：`"tutoring"`。
     * **路径**：`LearningPath` 重新生成。标题：`"更新学习路径，当前节点: {lp.current_node_name}"`，类型：`"path"`。
     * **资源**：`AsyncTask` 资源生成完成。标题：`"生成个性化资源"`，类型：`"resource"`。

### 任务 2: 防止空会话污染 Quiz 历史 (`GET /api/v1/quiz/questions`)
目前 GET 接口每次都会无条件创建一个 `QuizSession`。如果学生多次刷新页面或者返回后重新进入，会导致产生大量 `score=0` 且无答题记录的空会话，极大地拉低平均分并污染历史。
* **具体做法**：
  在 `get_questions` 下发新题目集并生成新 `QuizSession` 前，主动清理（soft-delete）该用户该课程下之前没有任何答题记录的空会话：
  ```python
  from sqlalchemy.sql import exists
  await db.execute(
      update(QuizSession)
      .where(
          QuizSession.user_id == current_user.id,
          QuizSession.course_id == course_id,
          QuizSession.is_deleted == False,
          ~exists().where(QuizAnswer.quiz_id == QuizSession.id)
      )
      .values(is_deleted=True)
  )
  ```

### 任务 3: 实现 refresh 异步任务重启时重试/恢复 (`app/main.py`)
原本当服务器重启时，`lifespan` 仅仅是把处于 `processing` 状态的 refresh 任务直接标记为 `failed`（止血处理）。
* **具体做法**：
  为了实现更好的可靠性，可以在 `main.py` 启动恢复逻辑中对这类状态的任务执行**断点重试**：
  1. 查找状态为 `processing` 且类型属于 `profile_refresh` / `evaluation_refresh` / `learning_path_refresh` 的任务。
  2. 针对每个任务，局部导入相应的业务 payload 拼装函数，如果拼装成功，则重新启动协程拉起后台调用：
     * 重新构建 payload，并调用其 background task 协程（如 `_run_profile_refresh_background`）重新发往 Agent。
     * 保持原来的 `task_id`，从而保证前端轮询不会因服务重启而中断或返回 500。
  3. 如果组装 payload 抛出异常（例如底层用户数据已经缺失），才落入 catch 分支，将该 task 标记为 `failed`，并记录 `recovery_failed` 错误码。

---

## 3. 对外契约影响核对

* **是否改变 Client API 契约**：`否`
  * 所有的参数、接口路径以及返回 JSON 结构完全保持不变，纯属 Backend 内部逻辑健全和数据精细化。
* **是否改变 Agent API 契约**：`否`
  * 对 Agent 的调用格式、Webhook 结构没有任何变动。

## 4. 下一步开发与联调推进顺序建议

以下旧顺序已暂停，不再作为当前执行计划：

1. ~~在 `app/api/v1/quiz.py` 中引入空 QuizSession 的清理逻辑。~~
   - result/history 已通过过滤无 QuizAnswer 会话解决统计污染。
2. ~~重构 `app/api/v1/teaching.py` 中的 `GET .../learning` 接口。~~
   - 教师端学生状态展示范围已扩大，必须先完成产品字段和数据来源确认。
3. ~~在 `app/main.py` 中完成 `_recover_orphaned_refresh_tasks()` 的拉起重试改造。~~
   - refresh 持久恢复仍需单独设计，不应在当前契约重构前优先实施。
