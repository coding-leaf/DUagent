# TeacherConsole 班级 Insights 最小聚合设计

> 新增班级级 Insights 最小真实聚合端点，替换当前真实模式下 `getConsoleInsights(courseId)` 返回 `data: null` 的空实现，并为后续移除 `TeacherConsole.jsx` 中 `{useMock && (...Insights...)}` 守卫提供真实 API 数据基础。

**日期：** 2026-06-06  
**状态：** 设计稿

---

## 1. 背景与目标

当前 `TeacherConsole` 的 Insights 区块仍由 `useMock &&` 守卫，只在 mock 模式下渲染；`teachingService.getConsoleInsights(courseId)` 在真实模式下返回 `data: null`，导致教师端班级概览无法在真实 API 环境下完成联调验收。

本设计新增一个班级级最小 SQL 聚合端点：

```http
GET /api/v1/teaching/classes/{class_id}/insights
```

首版目标不是做完整“AI 洞察”，而是解决 `TeacherConsole` 真实模式没有 Insights 数据，导致班级概览核心区块无法联调验收的问题。

---

## 2. 设计原则

1. **最小 SQL 聚合**：只使用已有 SQL 数据源，避免引入 Agent、行为采集、排名算法等新口径争议。
2. **真实联调优先**：首版只补齐 TeacherConsole 真实模式可验收的数据基础，不追求完整教师洞察产品化。
3. **口径与个体报告一致**：`weak_points_top` 沿用 `TeacherStudentReport.weak_points` 的聚合口径，降低解释成本。
4. **拒绝旧 mock 语义回流**：防止旧 mock 中的“覆盖率 / 重点关注学生 / 排名 / AI 总结”重新进入首版正式契约。
5. **空态明确**：无学生、无练习、无学习路径时返回可预测空态，不用 0 分或静态文案伪装真实数据。

---

## 3. 范围与非目标

### 3.1 在范围

- Client API 新增：`GET /api/v1/teaching/classes/{class_id}/insights`
- Backend 新增班级级聚合路由
- Frontend `teachingService.getConsoleInsights(courseId)` 真实模式接入正式端点
- `TeacherConsole.jsx` 移除 Insights 区块的 `useMock &&` 守卫，真实模式可展示班级统计数据
- Backend 测试覆盖权限、空态、平均分、练习次数、薄弱知识点 Top、路径节点状态分布
- Frontend lint/build 验证

### 3.2 非目标

首版不返回、也不在前端静态补齐以下能力：

- `overview`
- `focus_students`
- `coverage_rate`
- `ranking`
- `agent_summary`
- 动力指数
- 重点关注学生
- 班级排名
- Agent 生成的自然语言洞察
- 时间窗统计（例如本周、本月）
- 行为采集或阅读进度口径

这些能力如果后续要进入正式产品，必须重新设计契约，不能复用旧 mock 语义或在前端静态补齐。

---

## 4. API 契约

### 4.1 端点

```http
GET /api/v1/teaching/classes/{class_id}/insights
```

### 4.2 权限

- 复用当前 teaching 模块已有鉴权风格。
- 需要 `teacher` 或 `admin` 角色通过 `require_role("teacher", "admin")`。
- 首版复用现有 `_verify_teacher(class_id, current_user, db)`：即使角色为 `admin`，实际访问仍必须满足 `course.teacher_id == current_user.id`，admin 不额外绕过课程归属校验。
- 未登录：按现有认证依赖行为返回。
- 角色不符：按现有 `require_role` 行为断言。
- 课程不存在：返回 404。
- 非课程教师访问：返回 403。

### 4.3 响应结构

成功响应：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "avg_quiz_score": 78.5,
    "total_quiz_attempts": 32,
    "weak_points_top": [
      {
        "knowledge_point": "AVL树旋转",
        "error_count": 7,
        "total_attempts": 12,
        "error_rate": 0.58
      }
    ],
    "path_node_progress": {
      "completed": 12,
      "in_progress": 5,
      "recommended": 8,
      "pending": 20,
      "total_nodes": 45
    }
  }
}
```

### 4.4 字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `avg_quiz_score` | number \| null | 班级有效入班学生在该课程下所有 QuizSession 的平均分；无练习时为 `null` |
| `total_quiz_attempts` | integer | 班级有效入班学生在该课程下 QuizSession 总次数；无练习时为 `0` |
| `weak_points_top` | array | 班级薄弱知识点 Top 5，口径与个体报告 `weak_points` 一致 |
| `path_node_progress` | object | 班级所有已入班学生 LearningPath 节点状态数量分布 |

---

## 5. 聚合口径

### 5.1 有效学生范围

所有聚合均限定在当前课程有效入班学生范围内：

```text
CourseEnrollment.course_id = class_id
CourseEnrollment.is_deleted = false
```

`QuizSession.user_id` 和 `LearningPath.user_id` 必须属于该课程 `CourseEnrollment.student_id` 集合。仅写 `QuizSession.course_id = class_id` 不足以定义学生范围，因为理论上可能存在同课程 ID 但非有效入班学生的历史或脏数据。

如果班级没有任何有效入班学生，直接返回空态：

```json
{
  "avg_quiz_score": null,
  "total_quiz_attempts": 0,
  "weak_points_top": [],
  "path_node_progress": {
    "completed": 0,
    "in_progress": 0,
    "recommended": 0,
    "pending": 0,
    "total_nodes": 0
  }
}
```

### 5.2 avg_quiz_score / total_quiz_attempts

数据源：有效入班学生在该课程下的 `QuizSession`。

过滤条件：

```text
QuizSession.course_id = class_id
QuizSession.user_id in CourseEnrollment.student_id
QuizSession.is_deleted = false
CourseEnrollment.is_deleted = false
```

聚合规则：

```text
avg_quiz_score = AVG(QuizSession.score)
total_quiz_attempts = COUNT(QuizSession.id)
```

空态规则：

- 没有任何 QuizSession：`avg_quiz_score: null`
- 没有任何 QuizSession：`total_quiz_attempts: 0`

`avg_quiz_score` 空态必须使用 `null`，不要使用 `0`，避免被误解为“班级平均 0 分”。

### 5.3 weak_points_top

数据源：班级有效入班学生的 `QuizAnswer` + `QuizQuestion` + `QuizSession`。

过滤条件：

```text
CourseEnrollment.course_id = class_id
CourseEnrollment.is_deleted = false
QuizSession.user_id = CourseEnrollment.student_id
QuizSession.course_id = class_id
QuizSession.is_deleted = false
QuizAnswer.is_deleted = false
QuizQuestion.is_deleted = false
QuizQuestion.knowledge_point != ""
```

聚合规则：

```text
error_count = SUM(case((QuizAnswer.is_correct == False, 1), else_=0))
total_attempts = COUNT(QuizAnswer.id)
error_rate = error_count / total_attempts
```

实现注意：

- SQLAlchemy 应继续使用 `case()`，不要使用数据库方言函数，保持 SQLite/MySQL 均可运行：

```python
case((QuizAnswer.is_correct == False, 1), else_=0)
```

返回规则：

- 只返回 `error_count > 0` 的知识点
- 排序：`error_rate DESC, error_count DESC`
- 取 Top 5
- 过滤空 `knowledge_point`

返回结构沿用个体学生报告：

```json
{
  "knowledge_point": "AVL树旋转",
  "error_count": 7,
  "total_attempts": 12,
  "error_rate": 0.58
}
```

### 5.4 path_node_progress

数据源：有效入班学生在该课程下的 `LearningPath.nodes[]`。

过滤条件：

```text
CourseEnrollment.course_id = class_id
CourseEnrollment.is_deleted = false
LearningPath.user_id = CourseEnrollment.student_id
LearningPath.course_id = class_id
LearningPath.is_deleted = false
```

统计班级内所有已入班学生的 `LearningPath.nodes[].status` 节点状态数量。该指标表示“节点状态分布”，不是“学生人数分布”。

返回结构：

```json
{
  "completed": 12,
  "in_progress": 5,
  "recommended": 8,
  "pending": 20,
  "total_nodes": 45
}
```

状态规则：

- 只统计 `completed`、`in_progress`、`recommended`、`pending`
- `total_nodes` 为上述四类已知状态的数量总和
- 未知 `status` 首版忽略，不扩展 schema，不计入 `total_nodes`
- 没有任何 LearningPath：四类状态均返回 `0`，`total_nodes: 0`

---

## 6. Backend 设计

### 6.1 文件

- 修改：`backend/app/api/v1/teaching.py`
- 测试：建议新增或扩展 `backend/tests/test_teacher_class_insights.py`
- 契约：修改 `docs/10-client-api/Client-API.openapi.json`

### 6.2 路由

新增路由：

```python
@router.get("/classes/{class_id}/insights")
async def get_class_insights(
    class_id: str,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await _verify_teacher(class_id, current_user, db)
    ...
```

### 6.3 查询顺序

推荐实现顺序：

1. 调用 `_verify_teacher` 验证课程存在与归属。
2. 查询有效入班学生 ID 列表。
3. 如果学生 ID 列表为空，直接返回空态。
4. 聚合 `avg_quiz_score` 与 `total_quiz_attempts`。
5. 聚合 `weak_points_top`。
6. 聚合 `path_node_progress`。
7. 返回统一 envelope。

---

## 7. Frontend 设计

### 7.1 文件

- 修改：`frontend/src/api/services/teaching.js`
- 修改：`frontend/src/pages/TeacherConsole.jsx`

### 7.2 teachingService

`getConsoleInsights(courseId)` 在真实模式下调用正式端点：

```javascript
client.get(`/teaching/classes/${courseId}/insights`)
```

要求：

- 真实模式不得再返回 `data: null`
- 旧 mock-only 路径不得作为正式契约依据
- 是否彻底删除 mock 分支可留到 implementation plan 决定；但正式模式必须接入 `/teaching/classes/${courseId}/insights`

### 7.3 TeacherConsole 状态

当前页面用一个 `Promise.all` 同时加载学生列表和 Insights。首版设计要求分离错误处理：

- 维护 `studentsLoading`
- 维护 `studentsError`
- 维护 `insightsLoading`
- 维护 `insightsError`

或采用等价的分离错误处理方式。

要求：

- Insights 加载失败不影响学生列表展示
- 学生列表加载失败不应伪造成 Insights 空态
- 切换班级时重新加载学生列表与班级统计

推荐使用 `Promise.allSettled` 或两个独立请求实现隔离。

### 7.4 TeacherConsole 展示

移除 Insights 区块的 `useMock &&` 守卫，让真实模式也能渲染班级统计区块。

首版将该区块降级为班级统计区块，避免保留 AI 总结式单文案卡片结构，也避免标题继续表达为完整“AI 洞察”。

首版展示内容限定为：

- 平均练习分：`avg_quiz_score ?? "暂无数据"`
- 练习次数：`total_quiz_attempts`
- 薄弱知识点 Top：`weak_points_top`
- 路径节点状态分布：`path_node_progress`

错误文案使用中性统计口径，不复活“AI 洞察”语义：

```text
班级统计加载失败，请稍后重试。
```

空态文案示例：

```text
暂无班级统计数据
```

不展示 Agent 总结、不展示 overview 文案、不展示重点关注学生、不展示覆盖率、不展示排名。

---

## 8. OpenAPI 设计

在 `docs/10-client-api/Client-API.openapi.json` 中新增：

```text
GET /teaching/classes/{class_id}/insights
```

响应 schema 建议命名：

- `ClassInsights`
- `ClassWeakPoint`
- `PathNodeProgress`

成功响应包含：

- `avg_quiz_score`: nullable number
- `total_quiz_attempts`: integer
- `weak_points_top`: array of `ClassWeakPoint`
- `path_node_progress`: `PathNodeProgress`

错误响应至少与 teaching 模块既有端点保持一致：

- 401：未认证
- 403：无权访问此班级 / 角色不符按现有行为
- 404：课程不存在

---

## 9. 测试设计

### 9.1 Backend 测试

建议新增 `backend/tests/test_teacher_class_insights.py`，覆盖：

1. 未登录：按现有认证依赖行为断言。
2. 角色不符：按现有 `require_role` 行为断言。
3. 课程不存在：404。
4. 非课程教师访问：403。
5. admin 用户访问非自己课程：按现有 `_verify_teacher` 行为返回 403。
6. 班级无有效入班学生：返回空态。
7. 班级有学生但无 QuizSession：`avg_quiz_score: null`、`total_quiz_attempts: 0`。
8. `avg_quiz_score` 与 `total_quiz_attempts` 只统计有效入班学生。
9. `weak_points_top`：过滤空知识点、只返回 `error_count > 0`、排序 `error_rate DESC, error_count DESC`、Top 5。
10. `weak_points_top` 不统计非入班学生、软删除 session、软删除 answer、软删除 question。
11. `path_node_progress`：按所有有效入班学生的 `LearningPath.nodes[].status` 节点数量聚合。
12. `path_node_progress`：未知 status 忽略且不计入 `total_nodes`。
13. 没有任何 LearningPath：四类状态为 0，`total_nodes: 0`。

### 9.2 Frontend 验证

- `npm run lint`
- `npm run build`

如实现包含可稳定定位的 UI 内容，可补充前端单测或 E2E；若当前项目未建立组件测试体系，首版至少通过 lint/build 与后端聚合测试保障。

---

## 10. 风险与后续

### 10.1 风险

- `avg_quiz_score` 首版按所有 QuizSession 直接聚合，未做“先学生平均再班级平均”，解释简单但对练习次数较多的学生权重更高。
- `path_node_progress` 是节点状态分布，不是学生人数分布，前端文案必须避免误导。
- admin 首版不扩大课程归属权限；如后续需要 admin 全局可见，需要单独设计权限语义。

### 10.2 后续可扩展方向

以下能力需另起 spec：

- Agent 生成班级总结
- 重点关注学生
- 覆盖率
- 排名
- 时间窗趋势
- 学习时长与阅读进度
- 行为采集与活动摘要

---

## 11. 自审

- 无 `TBD` / `TODO` / 占位符。
- 端点使用完整路径：`GET /api/v1/teaching/classes/{class_id}/insights`。
- 响应结构完整且不包含旧 mock 字段。
- `avg_quiz_score` 空态明确为 `null`。
- 所有 Quiz 聚合均明确按 `CourseEnrollment.student_id` 有效学生范围过滤。
- `weak_points_top` 口径与个体报告一致，使用 `case()` 条件聚合。
- `path_node_progress` 明确是节点状态分布，不是学生人数分布。
- 非目标明确排除 overview / focus_students / coverage_rate / ranking / agent_summary。
- admin 权限不扩展，复用现有 `_verify_teacher` 语义。