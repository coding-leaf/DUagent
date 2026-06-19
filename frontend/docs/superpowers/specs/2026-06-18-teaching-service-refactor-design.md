# Teaching Service 分层重构设计（2026-06-19 修订）

## 背景

`backend/app/api/v1/teaching.py` 当前约 438 行，同时承担 FastAPI 路由、教师权限、学生归属校验、SQLAlchemy 查询、报表聚合和响应 DTO 组装。代码审查还确认了四类不能继续“等价搬迁”的问题：

1. 学生详情接口只验证课程归属，没有验证学生已加入该班级，可能泄露任意用户的邮箱、姓名和学号。
2. `evaluation_summary.overall_score` 固定返回 `75.0`，属于硬编码假数据。
3. 学生列表逐条查询 User，存在 N+1，并且分页查询没有稳定排序。
4. Evaluation、UserProfile、LearningPath 的读取没有统一的“最新有效记录”规则；后两者使用 `scalar_one_or_none()`，但数据库没有对应唯一约束，重复历史记录可能导致 500。

因此，本次不能沿用原计划的“完全保持当前行为”。设计目标改为：在同一 Teaching 模块边界内，先用测试锁定正确契约，再完成安全修复、数据真实性修复和分层重构。

## 目标

1. 采用 `Router -> TeachingService -> DB`，让 Router 仅保留 HTTP 边界职责。
2. 学生详情与学习报告统一校验：当前用户是任课教师，目标学生存在有效 enrollment。
3. 用 Evaluation 的真实 `mastery_table.rows[].average_score` 计算综合评分；没有有效数据时返回 `null`。
4. 消除学生列表 N+1，增加确定性分页排序。
5. Evaluation、UserProfile、LearningPath 明确选择最新有效记录。
6. 将 Quiz 汇总交给数据库聚合，避免加载全部 QuizSession 后在 Python 计算。
7. 保持前端已消费的响应结构和同步查询方式不变，并明确记录必要的 Client API 行为修正。
8. 在独立 MySQL 测试库中完成 TDD 与定向覆盖率验证。

## 非目标

- 不修改数据库表结构或索引；如后续 `EXPLAIN` 证明需要复合索引，另写 migration Spec。
- 不修改 Agent Service，不增加 Agent 调用或后台任务。
- 不引入 Repository、CQRS、缓存、工作流引擎或第三方依赖。
- 不修改前端页面；当前前端不展示 `overall_score`，但后端仍按 Client API 返回该字段。
- 不重构 `evaluation.py`、`profile.py`、`learning_path.py` 或其他路由。
- 不修改 `.env`、密钥、volume、用户上传内容或 catalog storage。

## 架构与模式选型

| 架构或模式 | 结论 | 原因 |
| --- | --- | --- |
| 分层架构 | 选用 | Router 负责 HTTP，TeachingService 负责权限和查询编排，符合项目现有样板。 |
| Service Layer | 选用 | 五个教师查询接口属于同一只读应用边界，适合集中管理一致的权限与聚合规则。 |
| Presenter/DTO | 在 Service 内使用私有纯函数 | 当前 DTO 数量有限，先避免额外文件；若 Service 实现后仍过大，再单独评审。 |
| Repository | 不选用 | 查询高度面向教师报表，增加通用数据访问接口只会增加跳转层。 |
| CQRS/Read Model | 不选用 | 当前数据规模和同步接口不需要独立读模型。 |
| 策略模式 | 不选用 | 当前没有可替换的多套统计算法。 |
| 缓存 | 不选用 | 先修正查询边界和复杂度，当前没有缓存失效设计需求。 |
| 数据库 migration | 不选用 | 本轮不改 schema；索引优化须有 MySQL `EXPLAIN` 证据后单独实施。 |

## 文件边界

### `backend/app/api/v1/teaching.py`

仅保留：

- `APIRouter` 和 route decorators；
- `Depends`、`Query` 与角色依赖；
- `TeachingService(db)` 调用；
- `{code, message, data}` 响应包装。

不得保留 SQLAlchemy 查询、聚合循环、权限查询或 DTO 细节。

### `backend/app/services/teaching_service.py`

新增 `TeachingService(db: AsyncSession)`，公开方法：

- `verify_teacher(class_id, current_user) -> Course`
- `list_students(class_id, current_user, page, page_size) -> dict`
- `get_student_info(class_id, student_id, current_user) -> dict`
- `get_student_learning(class_id, student_id, current_user) -> dict`
- `get_class_insights(class_id, current_user) -> dict`

内部 helper：

- `_require_enrolled_student(class_id, student_id) -> User`
- `_latest_evaluation(user_id, course_id) -> Evaluation | None`
- `_latest_profile(user_id, course_id) -> UserProfile | None`
- `_latest_learning_path(user_id, course_id) -> LearningPath | None`
- `_overall_score(mastery_table) -> float | None`
- DTO 组装所需的短小纯函数。

Service 可以直接使用 SQLAlchemy，不增加 Repository 接口。

### 测试文件

- 新增 `backend/tests/test_teaching_service.py`：Service 行为、权限、排序、评分和查询边界。
- 调整 `backend/tests/test_teacher_student_learning.py`：保持 HTTP 聚合回归，补充真实评分语义。
- 调整 `backend/tests/test_teacher_class_insights.py`：保持班级聚合与空态回归。

后端规则要求一次不超过 5 个文件；实施按独立小阶段提交，每个阶段只修改当阶段所需文件。

## 权限与错误语义

每个公开 Service 方法先执行 `verify_teacher()`：

- 课程不存在：HTTP 404，`{"code": 40400, "message": "课程不存在", "data": null}`。
- 当前用户不是任课教师：HTTP 403，`{"code": 40300, "message": "无权访问此班级", "data": null}`。

学生详情与学习报告随后执行 `_require_enrolled_student()`：

- 目标必须是未软删除用户，并具有该课程下未软删除的 enrollment。
- 用户不存在或未入班统一返回 HTTP 404，`{"code": 40400, "message": "学生未入班", "data": null}`，避免通过差异响应探测用户。
- 学生列表只通过有效 enrollment 返回用户，不返回已软删除用户。

保留当前 admin 行为：admin 能通过角色依赖，但若不是该课程 `teacher_id`，仍返回 403。本次不扩大 admin 数据访问范围。

## 查询与数据流

### 学生列表

1. 验证任课教师。
2. 查询有效 enrollment 总数。
3. 使用 `CourseEnrollment JOIN User` 一次读取当前页。
4. 按 `CourseEnrollment.create_time ASC, CourseEnrollment.id ASC` 排序后应用 offset/limit。
5. 返回现有 `students/total/page/page_size` 结构。

非空页查询次数固定，不随 `page_size` 增长。

### 单学生详情

1. 验证任课教师。
2. 通过 enrollment 与 User 的组合查询确认学生属于当前班级。
3. 返回现有账号基础资料字段。

### 单学生学习报告

1. 验证任课教师和 enrollment。
2. Evaluation 按 `generated_at DESC, create_time DESC, id DESC` 选择最新有效记录。
3. UserProfile 和 LearningPath 按 `generated_at DESC, create_time DESC, id DESC` 选择最新有效记录，使用 `LIMIT 1`，不依赖数据库中不存在的唯一约束。
4. QuizSession 使用 SQL 聚合获取 `count/avg(score)/avg(time_spent)`。
5. mastery breakdown 与 weak points 使用有界聚合查询；recent activity 只读取最新 5 条，并以 `create_time DESC, id DESC` 稳定排序。
6. 返回现有报告结构。

### 班级洞察

- 继续保持同步查询和现有响应字段。
- 使用 enrollment 子查询或 join 限定班级学生，避免先把任意规模的 `student_ids` 列表拼成 Python `IN` 参数。
- weak points 与 Quiz 聚合只统计有效 enrollment、QuizSession、QuizAnswer 和 QuizQuestion。
- LearningPath 当前仍需读取 JSON nodes 后在 Python 汇总；必须按每个学生的最新有效 LearningPath 统计，不能把历史路径重复计入。

## 综合评分真实口径

`_overall_score(mastery_table)` 的唯一数据源是最新 Evaluation 的 `mastery_table.rows`：

1. `mastery_table` 必须是 dict，`rows` 必须是 list。
2. 只读取 row dict 的 `average_score`。
3. 接受 int、float 或可安全转换的数字字符串；拒绝 bool、非数字、NaN、Infinity 和超出 0–100 的值。
4. 对有效值求算术平均并保留 1 位小数。
5. 没有有效值时返回 `None`，映射为 JSON `null`。

不使用 QuizSession 平均分冒充 Evaluation 综合评分，也不继续保留固定 `75.0`。

## Profile 统计语义

- `knowledge_mastered` 只统计 `status == "mastered"`。
- `knowledge_weak` 只统计 `status == "weak"`。
- `learning`、`pending`、`recommended`、`unstarted` 和未知状态不计入 weak。
- `modal_preference` 和 `knowledge_coordinates` 响应形态保持现状。

## Client 与 Agent 契约

### Client API

路径、query 参数和响应对象层级不变，但存在两项明确的行为修正：

1. `GET /teaching/classes/{class_id}/students/{student_id}` 对未入班用户由当前错误的 200 改为 404。
2. `evaluation_summary.overall_score` 从固定 number 改为真实 number；无有效 mastery 数据时允许 `null`。

需同步更新 Client API 文档中 `overall_score` 的 nullable 说明，并在 WORKFLOW 记录契约漂移。前端当前未消费该字段，无需页面修改。

### Agent API

无漂移。本次不调用或修改 Agent Service。

## 测试设计

所有验收测试使用独立 MySQL 测试库，不以 SQLite 结果替代 MySQL 行为。

### Service 测试

- 课程不存在、非任课教师、admin 非任课教师的错误语义。
- 未入班学生详情与学习报告均返回 404，且不泄露用户存在性。
- 学生列表过滤软删除数据、分页稳定、查询次数不随学生数增长。
- Evaluation/Profile/LearningPath 存在多条历史记录时选择最新有效记录。
- `_overall_score` 覆盖有效平均、数字字符串、bool、非法字符串、NaN、Infinity、越界值和空 rows。
- Profile 只把 `weak` 计入薄弱数量。
- Quiz 汇总、mastery breakdown、weak points、recent activity 保持字段、排序和空态语义。
- 班级洞察只统计有效 enrollment，并且每名学生只使用最新 LearningPath。

### HTTP 回归

- 保留现有路径、参数、状态码包装和字段结构。
- 补充学生详情未入班 404。
- 补充 `overall_score` number/null 两种响应。
- 空班级 insights 继续返回 `avg_quiz_score: null` 和全零 path progress。

### 验证门槛

- RED：先运行目标测试并确认因缺失行为失败。
- GREEN：最小实现通过目标测试。
- IMPROVE：完成分层和查询收口后运行全部 Teaching 回归。
- `teaching_service.py` 定向覆盖率不低于 80%。
- `py_compile` 通过。
- 检查 `teaching.py` 不再导入 SQLAlchemy 查询构造器或业务 ORM 模型。

## 实施阶段

1. 用 MySQL Service 测试锁定权限、最新记录、评分和 Profile 语义。
2. 新增 TeachingService 的权限与基础学生查询，修复未入班详情泄露和列表 N+1/排序。
3. 迁移单学生学习报告，落实真实评分、最新记录和数据库 Quiz 聚合。
4. 迁移班级洞察，限定有效 enrollment 与最新 LearningPath。
5. 精简 Router，运行 HTTP 回归、覆盖率和语法检查。
6. 更新 Client API nullable 说明、`WORKFLOW.md` 与 `docs/requirements-coverage.md`，分阶段提交。

## 验收标准

1. `teaching.py` 只保留 HTTP 边界职责，不包含 SQLAlchemy 查询或聚合算法。
2. 未入班用户不能通过学生详情或学习报告接口被读取。
3. 不再返回固定 `overall_score=75.0`；真实评分和 null 语义有测试。
4. 学生列表无 N+1 且分页稳定。
5. 重复历史 Evaluation/Profile/LearningPath 不导致 500，并按统一规则选择最新记录。
6. Quiz 汇总不加载全部会话到 Python 计算。
7. 相关 MySQL 回归全部通过，TeachingService 定向覆盖率不低于 80%。
8. Client API 漂移已记录，Agent API 明确无漂移。
