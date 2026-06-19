# Teaching Query 拆分设计

## 背景

`backend/app/services/teaching_service.py` 当前约 589 行。上一轮重构已经将 Teaching Router 精简为 HTTP 边界，并把权限校验、学生查询、单学生学习报告和班级洞察集中到 `TeachingService`。

当前 `get_student_learning()` 与 `get_class_insights()` 分别承担两组独立的只读聚合：

- 单学生学习报告需要组合最新 Evaluation、UserProfile、LearningPath、Quiz 统计、薄弱知识点和最近活动。
- 班级洞察需要限定有效 enrollment，聚合班级 Quiz、薄弱知识点排名和每名学生的最新 LearningPath。

两组查询的数据范围、响应 DTO 和变化原因不同。继续将它们保留在同一 Service 中，会使 `TeachingService` 再次成为胖 Service，并降低查询逻辑的独立可测试性。

## 目标

1. 保持 `TeachingService` 为 Router 的唯一入口和 Teaching 模块门面。
2. 将单学生学习报告拆入 `StudentReportQuery`。
3. 将班级洞察拆入 `ClassInsightsQuery`。
4. 将权限校验集中保留在 `TeachingService`，避免 Query 对象重复鉴权。
5. 保持现有 Client API 路径、参数、响应字段、nullable 语义和同步行为不变。
6. 通过独立 MySQL 测试锁定拆分前后的查询行为。

## 非目标

- 不修改 Router 路径、请求参数或响应 DTO。
- 不修改数据库表、索引或 migration。
- 不修改 Agent Service、Agent API、LLM、Prompt、RAG 或 Qdrant。
- 不引入完整 CQRS 基础设施、Repository、Query Bus、公共基类或依赖注入容器。
- 不引入缓存或第三方依赖。
- 不修改 `.env`、密钥、volume、用户上传文件或构建产物。
- 不顺带重构 Teaching 之外的业务模块。

## 方案比较

### 方案一：Service Facade + 专用 Query Object（选用）

`TeachingService` 保留公开接口、权限校验和简单学生查询，将两组大型只读聚合委派给专用 Query 对象。

优点：Router 无感知、权限边界集中、聚合职责清晰、Query 可独立测试。新增抽象数量有限，符合当前规模。

### 方案二：只拆私有函数模块（不选用）

将 SQL 查询移动为模块函数，但仍由 `TeachingService` 完成所有编排。

优点是改动较小；缺点是 `TeachingService` 仍掌握所有报表细节，职责和测试边界没有真正分开。

### 方案三：完整 CQRS + Repository（不选用）

增加 Query Handler、Repository 接口、独立 DTO 和分发机制。

隔离更彻底，但当前只有两组只读聚合，没有多存储实现、Query Bus 或跨模块复用需求，引入完整基础设施属于过度设计。

## 架构与模式选型

| 架构或模式 | 结论 | 原因 |
| --- | --- | --- |
| 分层架构 | 继续选用 | 保持 Router → TeachingService → Query → DB 的单向调用。 |
| Service Facade | 选用 | `TeachingService` 维持稳定公开入口，隐藏内部查询拆分。 |
| Query Object | 选用 | 两组复杂只读聚合具有独立数据范围和返回结构。 |
| CQRS | 仅采用查询职责分离思想，不引入框架 | 当前不需要 Command/Query Bus 或独立读模型。 |
| Repository | 不选用 | 查询高度面向报表，通用 Repository 会增加跳转并削弱 SQL 表达力。 |
| DTO/Presenter | 保留在各 Query 内 | 响应 DTO 分别属于两组聚合，无需增加单独层。 |
| 策略模式 | 不选用 | 没有可替换的多套报表算法。 |
| 缓存 | 不选用 | 本轮只做职责拆分，没有缓存一致性需求和性能证据。 |
| 中间件/责任链 | 不选用 | 痛点不是横切请求处理。 |

本设计中的 `Query` 是 Teaching 模块内部的应用查询对象，不代表引入完整 CQRS 架构。

## 文件与职责边界

### `backend/app/services/teaching_service.py`

保留：

- `TeachingService` 公开门面；
- `verify_teacher()`；
- `_require_enrolled_student()`；
- `list_students()`；
- `get_student_info()`；
- 四个供 Router 调用的公开方法。

调整：

- `get_student_learning()` 只完成任课教师校验、enrollment 校验，并调用 `StudentReportQuery.execute()`。
- `get_class_insights()` 只完成任课教师校验，并调用 `ClassInsightsQuery.execute()`。
- `_overall_score()` 和 `_ranked_modal_preferences()` 随其唯一消费者移动到学生报告查询模块。
- 最新 Evaluation、Profile 和 LearningPath 的查询 helper 随学生报告职责移动。

### `backend/app/services/student_report_query.py`

新增 `StudentReportQuery`：

```python
class StudentReportQuery:
    def __init__(self, db: AsyncSession): ...

    async def execute(self, class_id: str, student: User) -> dict: ...
```

职责：

- 选择学生最新有效 Evaluation、UserProfile 和 LearningPath；
- 计算真实综合评分、Profile 摘要和学习路径进度；
- 聚合 Quiz 统计与知识点正确率；
- 计算薄弱知识点；
- 查询最近五次 Quiz 活动；
- 组装现有单学生学习报告 DTO。

该对象接收已通过 enrollment 校验的 `User`，不自行查询课程权限或抛出权限类 HTTP 异常。

### `backend/app/services/class_insights_query.py`

新增 `ClassInsightsQuery`：

```python
class ClassInsightsQuery:
    def __init__(self, db: AsyncSession): ...

    async def execute(self, class_id: str) -> dict: ...
```

职责：

- 建立有效 enrollment 数据范围；
- 聚合班级 Quiz 平均分和总作答次数；
- 聚合班级薄弱知识点排名；
- 为每名学生选择最新有效 LearningPath；
- 汇总路径节点状态；
- 组装现有班级洞察 DTO 和空班级响应。

该对象仅在 `TeachingService.verify_teacher()` 成功后调用，不自行处理任课教师权限。

### Router

`backend/app/api/v1/teaching.py` 保持不变。Router 继续只实例化 `TeachingService`，不直接依赖两个 Query 对象。

## 调用与数据流

```text
FastAPI Router
  → TeachingService
      → 任课教师校验
      → 学生 enrollment 校验（仅学生查询）
      → StudentReportQuery / ClassInsightsQuery
          → SQLAlchemy AsyncSession
          → 现有响应 DTO
```

### 单学生学习报告

1. Router 调用 `TeachingService.get_student_learning()`。
2. `TeachingService` 验证课程存在且当前用户为任课教师。
3. `TeachingService` 验证目标学生是有效 enrollment，并获得 `User`。
4. 使用同一个 `AsyncSession` 创建 `StudentReportQuery`。
5. Query 读取和聚合真实数据，返回现有 DTO。

### 班级洞察

1. Router 调用 `TeachingService.get_class_insights()`。
2. `TeachingService` 验证课程存在且当前用户为任课教师。
3. 使用同一个 `AsyncSession` 创建 `ClassInsightsQuery`。
4. Query 在有效 enrollment 范围内聚合数据并返回现有 DTO。

Query 对象不创建新事务、数据库连接或 session，也不提交数据；全部查询保持只读。

## 查询语义保持

本轮是结构重构，不改变上一轮已经验证的业务语义：

- Evaluation、UserProfile、LearningPath 继续按 `generated_at DESC, create_time DESC, id DESC` 选择最新有效记录。
- 综合评分继续只使用有效的 `mastery_table.rows[].average_score`，无有效值时返回 `null`。
- Profile 只将 `status == "weak"` 计入薄弱数量。
- Quiz 聚合继续排除软删除的 Session、Answer 和 Question。
- recent activity 继续按 `create_time DESC, id DESC` 返回最多五条。
- 班级洞察只统计有效 enrollment。
- 班级路径进度继续为每名学生只统计最新有效 LearningPath。
- 空班级继续返回 `avg_quiz_score: null`、零作答次数、空薄弱点和全零路径进度。

## 错误处理与契约

权限和资源错误继续由 `TeachingService` 产生：

- 课程不存在：HTTP 404，保持现有错误 DTO。
- 当前用户不是任课教师：HTTP 403，保持现有错误 DTO。
- 学生不存在或未入班：HTTP 404，统一返回“学生未入班”。

两个 Query 对象不捕获数据库异常，不将异常转换成空数据或伪造结果。数据库异常继续交给现有 FastAPI 全局异常机制处理。

### Client API

无契约漂移：路径、参数、响应字段、nullable 语义、状态码和同步行为全部保持不变。

### Agent API

无契约漂移：本轮不调用或修改 Agent Service。

## 测试设计

所有数据查询测试继续使用独立 MySQL 测试库，不以 SQLite 替代。

### `backend/tests/test_teaching_service.py`

保留并聚焦：

- `verify_teacher()` 权限和错误契约；
- 未入班学生不可读取；
- 学生列表排序、软删除过滤和无 N+1；
- `TeachingService` 向两个 Query 委派时传入正确的已验证范围。

### `backend/tests/test_student_report_query.py`

新增或迁移：

- 综合评分纯函数边界；
- 多条 Evaluation/Profile/LearningPath 时选择最新有效记录；
- Profile 状态和模态偏好汇总；
- Quiz 汇总和知识点正确率；
- 薄弱点排序；
- recent activity 数量与稳定排序；
- 缺少各类数据时的 nullable 和空态。

### `backend/tests/test_class_insights_query.py`

新增或迁移：

- 只统计有效 enrollment；
- 班级 Quiz 平均分和总次数；
- 薄弱点排名；
- 每名学生只使用最新 LearningPath；
- 未知节点状态不进入已知状态计数；
- 空班级响应。

现有 HTTP 回归测试继续验证 Router 路径、响应包装和字段结构。

## TDD 与实施阶段

### 阶段一：Student Report Query

1. 将单学生报告测试迁移或补充到独立测试文件。
2. 运行测试，确认因目标 Query 尚不存在而失败。
3. 新增 `student_report_query.py`，迁移相关 helper 和聚合逻辑。
4. 将 `TeachingService.get_student_learning()` 收缩为校验与委派。
5. 运行学生报告、TeachingService 和 HTTP 定向回归。
6. 提交本阶段文件。

### 阶段二：Class Insights Query

1. 将班级洞察测试迁移或补充到独立测试文件。
2. 运行测试，确认因目标 Query 尚不存在而失败。
3. 新增 `class_insights_query.py`，迁移班级聚合逻辑。
4. 将 `TeachingService.get_class_insights()` 收缩为校验与委派。
5. 运行班级洞察、TeachingService 和 HTTP 定向回归。
6. 提交本阶段文件。

### 阶段三：完整验证与记录

1. 运行全部 Teaching 回归。
2. 运行修改 Python 文件的 `py_compile`。
3. 检查两个 Query 文件的定向覆盖率均不低于 80%。
4. 确认 Router 未新增 SQLAlchemy 或业务模型依赖。
5. 更新 `WORKFLOW.md` 与 `docs/requirements-coverage.md`。
6. 记录 Client API 和 Agent API 均无漂移，并提交记录。

每个实施提交不超过 5 个文件，不纳入工作区内与本任务无关的已有修改。

## 验收标准

1. Router 继续只依赖 `TeachingService`，代码和对外行为不变。
2. `TeachingService` 保留权限边界和公开门面，不再包含两组大型报表 SQL 与 DTO 组装。
3. `StudentReportQuery` 和 `ClassInsightsQuery` 各自具有单一、明确的数据范围和输出。
4. Query 对象复用调用方的 `AsyncSession`，不创建事务或写入数据库。
5. 权限、最新记录、软删除过滤、评分和空态语义均保持现有行为。
6. 相关 MySQL 测试、HTTP 回归和语法检查全部通过。
7. 两个 Query 文件的定向测试覆盖率均不低于 80%。
8. Client API 与 Agent API 均无契约漂移。
