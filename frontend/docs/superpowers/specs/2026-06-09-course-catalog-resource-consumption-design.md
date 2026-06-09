# CourseCatalog 资源消费闭环设计

## 目标

本 spec 定义第一版“资源消费闭环”的产品口径：Admin 生产资源，Teacher 查看确认，Student 消费学习资源。

本轮不设计 AI Chat、Quiz 生成、LearningPath 刷新或 KG ready gate。AI Chat 后续单独开 spec，且从“先验证 Agent 检索能力”开始，不先加 UI。

## 范围

第一版产品规则：

- Admin 是资源生产方：创建 CourseCatalog、上传原始资料、触发入库、触发资源库级学习资源生成、软删除资料/资源。
- Teacher 是资源使用确认方：创建教学班时绑定 ready CourseCatalog；之后能在教师端查看本班绑定的资源库状态、本班可见资源列表和资源详情。
- Student 是学习消费方：只看到本班学习资源列表和详情，不看到 Admin 上传的原始资料。
- 资源第一版按班级存、按班级读：生成结果 fan-out 到当前已绑定该 CourseCatalog 的教学班，学生/教师都通过教学班 `course_id` 消费资源。
- 新教学班不会自动回补历史生成资源；如果本班暂无资源，教师端提示联系管理员生成，学生端显示准备中空态。

## 数据与归属

第一版沿用当前数据所有权，并把契约级结构标为“已核实的当前代码事实”：

- `CourseCatalog`：课程资源库，代表一组 Admin 管理的资料和知识库状态。
- `CourseCatalogMaterial`：Admin 上传的原始资料，只作为入库和生成素材；学生端不展示。
- `CourseOffering`：教学班与 CourseCatalog 的绑定关系。当前创建教学班时，Backend 在 `../backend/app/api/v1/courses.py:134` 的 `if catalog is not None` 分支写入 `CourseOffering(id=course.id, catalog_id=catalog.id)`，因此当前绑定资源库的链路事实是 `CourseOffering.id == Course.id`。legacy 无 catalog 的 course 不产生 offering。
- `Resource`：学生/教师可消费的学习资源，第一版仍归属具体教学班 `course_id`。
- `AsyncTask`：入库和资源生成任务状态，前端只通过 `/tasks/{task_id}` 轮询，不感知 Agent webhook。

资源生成规则：

- Admin 在资源库级触发生成。
- Backend 调 Agent 时使用 CourseCatalog 作为检索上下文：在 `../backend/app/api/v1/catalogs.py:893` 的 Admin 资源生成 payload 中，`course_id` 传的是 `catalog.id`。
- Backend 同时记录当前绑定该 catalog 的 `fanout_course_ids`。Agent webhook 完成后在 `../backend/app/api/v1/webhooks.py:103` 按这些教学班 id 写入 `Resource.course_id`。
- fan-out 目标班级取自触发生成时写入 `task.result.fanout_course_ids` 的快照（`../backend/app/api/v1/webhooks.py:105`），因此“晚建班无历史资源”的本质是它不在该快照内。

## 已知演进方向

`资源库中心`模式是明确登记的后续方向：资源归属 CourseCatalog，多班按 catalog 读取或引用。

触发条件：出现真实需求，即一个 CourseCatalog 绑定多个教学班，并且需要历史资源自动同步、跨班复用、统一更新或统一删除时，再启动接口级重构。

在触发前，不提前引入 catalog-level resource 读取、引用表或自动回补逻辑。

## 学生体验

学生端第一版只消费“本班学习资源”，不展示 Admin 上传的原始资料。

学生进入课程后：

- 课程选择仍沿用当前 `CourseContext` / `/courses` 逻辑。
- 资源列表继续按当前教学班 `course_id` 调 `GET /resources`。
- `Dashboard.jsx` 有两个不同空态，不能混：
  - 无课程分支：当前在 `src/pages/Dashboard.jsx:82`，继续显示“暂无课程 / 请先加入一门课程”，不改。
  - 有课程但资源为空分支：当前在 `src/pages/Dashboard.jsx:262`，保留 `data-testid="resources-empty"`，仅把 title/description 从“暂无资源 / 当前课程暂无学习资源”改为“课程资源正在准备中 / 请稍后查看”。
- 不向学生解释 CourseCatalog、fan-out、管理员生成、原始资料等后台概念。
- 不新增学生侧“生成资源”“请求生成”“查看原始资料”入口。
- 不在这份 spec 里改变 Quiz、AI Chat、LearningPath 的学生入口。

资源详情：

- 继续按 `GET /resources/{id}` 读取本班资源详情。
- 文档/阅读类显示正文或预览；mindmap/code 按现有展示能力处理。
- 当前 `src/pages/ResourceDetail.jsx:99` 没有显式 404/403 错误态，失败时会 `setResource(null)`；这不是理想体验，但本 spec 第一版不把它扩大成错误处理专项。
- 若后续实现资源详情错误态，只允许基于真实 API 错误显示“资源不存在 / 无权访问 / 加载失败”，不得回退假资源内容。

## 教师体验

教师端第一版做“查看”，不做资源管理和生成。

教师进入 `TeacherConsole` 后：

- 课程/班级列表继续按现有 `/courses` 读取。
- 对绑定了 CourseCatalog 的教学班，展示资源库名称或资源库绑定状态，帮助教师知道这个班级来自哪个资源库。
- 教师可以查看本班可见学习资源列表，读取口径与学生一致：按当前教学班 `course_id` 读取资源。
- 教师可以打开资源详情，确认学生将看到的内容。
- 教师端不出现“生成资源”“重新生成”“删除资源”“上传原始资料”入口。
- 如果本班暂无资源，教师端显示明确兜底：“本班暂无学习资源，请联系管理员生成”。
- 对 legacy 无 CourseCatalog 绑定的课程，不强行套入资源库流程；显示为未绑定资源库或保持当前课程视图，避免误导。

## 流程与错误口径

主流程按“Admin 生产，Teacher 确认，Student 消费”串联：

1. Admin 创建 CourseCatalog，上传原始资料并入库。
2. Admin 在资源库级生成标准学习资源。
3. Backend 在生成完成时，把资源 fan-out 到触发时已绑定该 CourseCatalog 的教学班。
4. Teacher 创建/查看教学班，确认绑定资源库和本班资源可见情况。
5. Student 加入教学班，通过资源列表和详情消费本班资源。

错误与空态口径：

- 学生有课程但无资源：“课程资源正在准备中 / 请稍后查看”。
- 教师本班无资源：“本班暂无学习资源，请联系管理员生成”。
- legacy 无资源库绑定课程：不阻断现有课程查看，不伪装成 CourseCatalog-ready 班级。
- 资源被软删除：列表不可见；详情若后续补错误态，只显示真实错误，不回退假数据。
- Admin 原始资料删除导致 CourseCatalog `dirty`：学生/教师已 fan-out 的未软删资源仍可见；是否需要重新生成由 Admin 侧判断，不在学生端暴露。

## 非目标

- 不恢复教师端 `/resources/generate`。
- 不接学生端生成资源或请求生成入口。
- 不展示 Admin 原始资料给学生。
- 不改 AI Chat、Quiz、LearningPath。
- 不设计 catalog-level resource API；仅登记为后续演进方向。
- 不做新教学班历史资源自动回补。

## 验证范围

后续实现验收应以“资源消费口径被正确表达”为准，不重新验收完整生成质量。

学生端 Dashboard：

- 无课程时仍显示“暂无课程 / 请先加入一门课程”。
- 有课程但资源为空时，`data-testid="resources-empty"` 仍存在，文案变为“课程资源正在准备中 / 请稍后查看”。
- 有资源时仍按真实 `/resources?course_id=...` 展示资源列表，不使用 mock 或假资源。

教师端：

- 教师课程/班级视图能看出绑定资源库状态。
- 教师能查看本班资源列表和详情。
- 教师端不出现生成、上传、删除资源入口。
- 本班无资源时显示“本班暂无学习资源，请联系管理员生成”。

链路回归：

- 保留 Admin 资源生成和软删除 E2E，防止 Admin 入口退化。
- 增加或调整教师/学生资源消费 E2E，覆盖空态和有资源态。
- 运行 `npm run lint`、`npm run build`。
- 若实现触及 Backend API，再补对应 pytest；若只写产品口径和前端文案，则不要求 Backend 测试。
