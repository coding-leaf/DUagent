# 资源库知识图谱宿主课兼容层设计

日期：2026-06-12

## Summary

当前资源消费模型已经切换为“教学班绑定资源库、资源按资源库共享读取”，但管理员资源库知识图谱链路仍依赖 `CourseKnowledgeGraph.course_id`。这导致未绑定任何教学班的新资源库无法触发：

- `POST /api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`
- `GET /api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs`

当前行为是直接返回 `40915: 课程资源库尚未绑定教学班`，与资源库中心模型冲突。

本设计不立即把知识图谱全量迁移为 `catalog_id` 主归属，而是增加一个“资源库宿主课”兼容层：

- 每个资源库可以拥有一个系统内部宿主 `course_id`
- 宿主课只用于承载 `course_knowledge_graphs`、相关任务上下文和 active KG 读取
- 宿主课不作为教师/学生真实教学班入口，不参与教学班列表、选课、加入课程等前端业务
- 已绑定教学班的资源库继续兼容当前行为，但管理员 KG 入口统一按“资源库宿主课”解析，不再要求先绑定教学班

该方案目标是先解除管理员侧 409 阻塞，并将“资源库宿主课”作为当前接受的长期过渡方案保留。知识图谱彻底迁移到 `catalog_id` 主归属不属于当前排期，后续无限期后置，不作为本阶段前置承诺。

## Problem

### 现状冲突

1. 资源已按 `catalog_id` 共享读取，但知识图谱仍按 `course_id` 存储。
2. Admin KG generation 接口在启动任务前要求资源库必须先找到一个 `CourseOffering`。
3. Admin KG status 接口同样通过“第一个绑定教学班”的 `course_id` 去读取 active KG。
4. 因此新资源库即使资料已入库、知识切片已 ready，只要未绑定教学班，就无法生成或查看图谱。

### 根因

`CourseKnowledgeGraph` 的表结构和服务函数仍以 `course_id` 为唯一归属键，典型依赖点包括：

- `course_knowledge_graphs.course_id`
- `get_active_knowledge_graph(db, course_id)`
- `create_knowledge_graph_version(..., course_id=...)`
- `generate_knowledge_graph_version(course_id=...)`

这条链路还没有完成从“课程中心”到“资源库中心”的迁移。

## Goals

- 允许未绑定教学班的资源库直接生成知识图谱
- 允许未绑定教学班的资源库查看 active KG 和最近任务状态
- 不破坏现有 LearningPath、节点资源、KG 版本服务对 `course_id` 的依赖
- 不把宿主课暴露给教师/学生前端使用
- 保留未来迁移到 `catalog_id` 的可能性，但不把它作为当前实施或近期收尾条件

## Non-Goals

- 本轮不把 `CourseKnowledgeGraph` 改成 `catalog_id` 主归属
- 本轮不改 LearningPath、节点资源、Evaluation/Profile 对 KG 的读取主键
- 本轮不做历史 KG 数据迁移
- 本轮不重构教师/学生端 KG 消费链路
- 本轮不顺带修复 Admin 资源生成接口对“必须绑定教学班”的旧限制

## Approaches Considered

### Approach A: 删除“必须绑定教学班”校验，继续复用第一个教学班

优点：
- 改动最小

缺点：
- 无绑定教学班时仍没有可用 `course_id`
- 只是去掉报错，不能真正落库或读取 active KG
- 设计上不完整

结论：
- 不可用，不能选

### Approach B: 引入资源库宿主课兼容层

优点：
- 不改 KG 主表结构即可解除 409
- 可复用现有 KG 版本服务、任务轮询、active KG 读取逻辑
- 改动集中，适合当前阶段止血

缺点：
- 增加一层兼容结构，但这是当前接受的长期过渡成本
- 需要明确“宿主课不可进入真实业务”的隔离规则

结论：
- 推荐方案

### Approach C: 直接把 KG 主归属迁移到 `catalog_id`

优点：
- 模型最干净，和资源库中心方向完全一致

缺点：
- 会波及 KG 服务、LearningPath、节点资源、active KG 读取、历史数据兼容
- 不是当前 bug 的最小修复，风险和联动范围过大

结论：
- 当前不采纳，并无限期后置

## Recommended Design

### 1. 宿主课定义

为每个 `CourseCatalog` 允许解析出一个“资源库宿主课” `course_id`。

宿主课规则：

- 宿主课是一个可持久化的 `courses` 记录
- 宿主课由系统自动创建或复用，不依赖教师手工绑定教学班
- 宿主课不出现在教师/学生的课程列表中
- 宿主课不允许学生加入
- 宿主课不作为真实教学班承载学生、教师教学行为

宿主课只承担以下职责：

- 承载 `CourseKnowledgeGraph.course_id`
- 承载 KG generation AsyncTask 的 `course_id`
- 为需要 `course_id` 的既有 KG 服务提供兼容入口

### 2. 宿主课解析策略

管理员资源库 KG 相关接口统一走：

1. 若资源库已存在系统宿主课，直接复用
2. 若不存在系统宿主课，则自动创建
3. 若资源库同时已有真实教学班，不再用“第一个教学班”作为 KG 主宿主；新接口优先统一走系统宿主课

这样可以避免：

- active KG 漂移在某个真实教学班下
- 后续新增/删除教学班时 KG 状态读取不稳定
- 管理员图谱状态依赖“第一个绑定教学班”这种偶然顺序

### 3. 对外行为

#### 管理员知识图谱生成

`POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`

改为：

- 不再要求资源库必须先绑定教学班
- 仅要求资源库存在，且知识切片满足当前 KG 生成前置条件
- 接口内部解析宿主课 `course_id`
- 任务仍按现有 `kg_generation` 类型创建
- `task.result.catalog_id` 保持保留，`course_id` 改为宿主课 id

#### 管理员知识图谱状态读取

`GET /admin/course-catalogs/{catalog_id}/knowledge-graphs`

改为：

- 通过资源库宿主课读取 active KG
- 返回的 `course_id` 改为宿主课 id
- 前端不再把该字段解释为“当前被教学班 X 使用”

#### 管理员文案

资源库详情中的知识图谱区应改为更准确的口径：

- 有 active KG 时：显示图谱版本与任务状态
- 无 active KG 时：显示“当前资源库暂无 active 知识图谱”
- 不再把“是否绑定教学班”作为 KG 区域的前置提示

## Data Model Strategy

本轮优先最小实现，推荐先不改 `course_knowledge_graphs` 表结构，只增加“宿主课标识如何反查资源库”的最小存储。

可选实现中，推荐顺序如下：

1. 在 `CourseCatalog` 增加 `kg_host_course_id`
2. 宿主课创建后回写到资源库
3. KG 相关接口统一以该字段解析宿主课

理由：

- 一对一关系清晰
- 不需要从 `CourseOffering` 反推
- 若未来确实启动迁移，该字段和关系也易于移除

不推荐：

- 继续从第一个 `CourseOffering` 推导
- 仅靠命名约定推断宿主课

## Backend Changes

### 路由与服务

需要调整：

- `backend/app/api/v1/catalogs.py`
  - 新增“获取或创建资源库宿主课” helper
  - `GET /admin/course-catalogs/{catalog_id}/knowledge-graphs`
  - `POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`

可能需要同步微调：

- `backend/app/services/course_knowledge_graphs.py`
- `backend/app/services/kg_generation.py`

### 宿主课创建规则

自动创建时：

- 创建一条系统 `Course`
- `teacher_id` 使用可审计的系统归属策略
- `course_code` 必须唯一，但不面向真实用户使用
- 不创建学生 enrollment
- 不创建 `CourseOffering`

关键要求：

- 宿主课必须能满足 `CourseKnowledgeGraph.course_id -> courses.id` 外键
- 但不能被普通课程列表当成真实教学班暴露出去

### 课程列表隔离

若当前 `/courses` 查询会读取全部 `courses`，需要增加过滤，确保系统宿主课不会出现在：

- 教师端课程列表
- 学生端课程列表
- 加入课程逻辑

这部分若当前已有足够业务过滤，可不额外修改；若没有，必须补隔离标识。

## Frontend Changes

### Admin 资源库抽屉

`CourseCatalogDrawer.jsx` 需要调整：

- KG 区描述从“当前被教学班使用/尚未被教学班使用”改为资源库视角
- 新资源库未绑定教学班时，仍允许点击“刷新图谱”
- `40915` 不再应成为正常阻塞态

### 非 Admin 页面

教师端、学生端本轮不新增入口，不应感知宿主课存在。

## Error Handling

- 保留现有“知识库未 ready / chunk 为空 / 任务进行中”等校验
- 删除 KG generation 对“必须绑定教学班”的 409 前置限制
- 宿主课创建失败时返回新的明确错误，而不是复用 `40915`
- 若宿主课存在但已损坏，应返回可定位的内部错误码，避免前端只看到通用 `Network Error`

## Testing

必须新增或更新以下用例：

1. 未绑定教学班但知识库已 ready 的资源库：
   - `POST /knowledge-graphs/generations` 返回 `202`
2. 同场景下：
   - `GET /knowledge-graphs` 初始返回 `course_id=<host_course_id>` 或 `active_graph=null`
   - 任务完成后返回 active KG
3. 已绑定教学班的资源库：
   - 生成与读取仍可正常工作
4. 宿主课隔离：
   - 不出现在普通 `/courses` 列表
5. 回归：
   - 现有 `test_admin_catalog_kg_generation.py`
   - 现有 `test_node_resources.py` 不应因本轮兼容层破坏

## Risks

### 风险 1：宿主课泄漏到真实课程列表

这是本方案最大风险。如果宿主课被教师或学生看到，会污染课程上下文、课程码体系和权限判断。

缓解：

- 明确系统标识
- `/courses` 查询层增加过滤
- 补隔离测试

### 风险 2：真实教学班与宿主课并存导致 KG 读取口径不一致

如果部分接口仍读“第一个教学班”，部分接口改读宿主课，会出现 Admin 看见一个 KG、LearningPath 读另一个 KG 的漂移。

缓解：

- 本轮至少把 Admin KG 相关入口统一切到宿主课
- 教学侧其余依赖保持现状，不在本轮扩展处理

### 风险 3：资源库中心资源与课程中心 KG 长期并存

系统会在可预见周期内保留“资源库中心资源 + 课程中心 KG”的双轨模型。

缓解：

- 明确宿主课只服务于 KG 承载，不扩散到教师/学生主链路
- 不为了未来迁移提前引入更大抽象层
- 在 feature ledger 和 workflow 中明确记录这是当前接受的长期过渡方案

## Long-Term Position

当前长期立场如下：

- 资源库宿主课兼容层不是一次性临时 hack，而是当前接受的过渡方案
- 只要它不泄漏到教师/学生真实业务，就可以持续使用
- “KG 完整迁移到 `catalog_id`”保留为未来可能方向，但无限期后置
- 当前不为未来迁移预埋额外复杂抽象，不扩大本轮范围

## Acceptance Criteria

- 新建资源库未绑定任何教学班时，管理员可直接发起 KG generation，不再收到 `40915`
- 同一资源库的 KG 状态读取不再依赖“第一个绑定教学班”
- 宿主课不会出现在教师/学生课程列表或加入课程流程
- 已绑定教学班的资源库保持现有 KG 能力不回归
- 本轮不要求 LearningPath 立即改为按 `catalog_id` 读取
