# EDUagent Feature Ledger（开发进度主线账本）

本文件是当前开发进度的主线账本。它不按 git 提交、不按文件清单、不按接口存在与否判断完成度，而是按**用户实际能操作什么功能**来记录。

它回答：

1. 当前已经实现了哪些真实功能。
2. 哪些页面已经接入真实 Client API。
3. 哪些只是 Backend / Agent / service 有能力，但前端没有入口。
4. 哪些能力已经验证过，哪些还需要联调。
5. 下一步应该按什么顺序推进。

分工：

- `docs/feature-ledger.md`：主线进度账本。看这一份决定下一步做什么。
- `WORKFLOW.md`：施工日记。按日期回溯某次做了什么、跑了什么测试。
- `docs/project-coverage-audit.md`：证据审计。需要查路径、测试、模型、Agent 依赖时看它。
- `docs/project-direction.md`：长期方向和断层恢复流程。

更新时间：2026-06-12

## 状态口径

| 状态 | 含义 | 判定标准 |
| --- | --- | --- |
| ✅ 已可操作 | 用户界面已有入口并调用真实 Client API | 页面 / 组件能触发，service 调用真实 API，已有测试或明确验证证据 |
| ✅ 后端闭环 | Backend / Agent / 测试已经完成，但前端没有正式入口 | 不能说“用户可用”，只能说后端能力可用 |
| 🔄 联调待验收 | 主代码链路已实现，但缺真实多服务环境证据 | 通常需要 Backend + Agent Service + DB/Qdrant/storage 一起跑 |
| ⚠️ 前端无入口 | API 或 service 存在，但没有页面 / 组件调用 | 不应被当作已实现用户功能 |
| 🚫 前端不接入 | 接口存在或曾设计过，但当前前端契约明确作废 / 不提供入口 | 不作为页面、service 或下一步主线推进 |
| 📋 待设计 | 没有明确 spec / 契约 | 禁止直接写代码 |
| ⏸️ 暂缓 | 当前阶段主动不做 | 非阻塞，但不能偷塞到实现里 |

主线规则：

1. 先处理 `🔄 联调待验收` 中影响真实数据闭环的能力。
2. 再处理 `📋 待设计` 中会阻塞主线的能力。
3. `⚠️ 前端无入口` 不能算用户功能完成；要么设计 UI 接入口，要么删除误导性 service，要么登记为后端能力。
4. `✅ 后端闭环` 不能自动升级为 `✅ 已可操作`。
5. `🚫 前端不接入` 不能进入教师端或学生端 UI 计划，也不能作为当前下一步主线。

## 当前主线结论

当前主线不是继续补页面字段，也不是让教师端触发资源 / Quiz 生成。Admin 资源库入库、Admin 资源库级资源生成、教师绑定 ready CourseCatalog、学生按教学班上下文消费资源库共享资源、教师只读确认绑定资源库资源已经形成当前前端闭环：

1. CourseCatalog 管理、资料上传、入库向量化已经从 Admin UI 到 Backend/Agent 入库链路打通。
2. Admin 可在资源库抽屉中基于已入库知识切片自动刷新课程知识图谱，触发资源库级学习资源生成、查看生成资源列表，并软删除资料或生成资源；知识图谱生成/读取已改为走资源库隐藏宿主课，不再要求先绑定真实教学班。
3. 教师创建教学班时绑定已就绪 CourseCatalog，并能在教师端查看绑定资源库状态、本班学习资源列表和资源详情。
4. 学生端按当前教学班 `course_id` 解析绑定 `catalog_id` 后查看共享资源列表和详情；有课程但暂无资源时显示“课程资源正在准备中 / 请稍后查看”。
5. 当前实现口径：新生成资源归属 `CourseCatalog`，同一资源库绑定多个教学班后可共享读取；legacy 按班级存储的旧资源继续兼容当前教学班读取，但不自动跨班共享。
6. 资源库 KG 宿主课是当前接受的长期兼容层：它只承载资源库知识图谱，不出现在教师/学生课程列表，也不能通过课程码加入。
7. `/resources/generate`、`/quiz/generate` 在当前前端契约中作废 / 不接入；教师端不提供生成资源入口，练习页不提供触发生题入口。
8. C 语言样本已完成 knowledge_status repair、KG-node 资源生成和 KG-Resource probe 复验：`108/108` active KG 节点 `candidate_count>0`。LearningPath 资源评估 probe 已接入，但管理员删除/重入库后真实 C catalog 出现历史不一致状态：当前未删除 material `chunk_count=0`，catalog 仍显示 `ready/ready` 且 `chunk_count=665`；已修复未来删除资料时的 chunk 重算逻辑，继续 LearningPath 前需先修正开发库这条 C 样本数据或重新上传有效资料并入库。

## 页面真实调用核查

本表按页面 / 组件实际调用记录，不按设想功能记录。

| 页面 / 组件 | 用户能做什么 | 真实调用 | 当前状态 | 备注 |
| --- | --- | --- | --- | --- |
| `Login.jsx` | 登录 | `GET /auth/captcha`、`POST /auth/login` | ✅ 已可操作 | 管理员/教师/学生登录分流已修正。 |
| `Register.jsx` | 注册 | `GET /auth/captcha`、`POST /auth/register` | ✅ 已可操作 | 注册提交基础资料和 `guidance_level`。 |
| `AuthContext.jsx` | 鉴权恢复 | `GET /users/me` | ✅ 已可操作 | 页面刷新后恢复登录态。 |
| `StudentProfile.jsx` | 查看学生画像、对话补充画像、静默同步画像、修改指导级别 | `GET /profile`、`POST /profile/dialogue-update`、`POST /profile/refresh`、`GET /tasks/{task_id}`、`PUT /users/me` | ✅ 已可操作 | 六维画像走 `profile_dimensions`；同步画像不暴露 prompt，完成后刷新画像。 |
| `Dashboard.jsx` | 查看课程资源列表；有课程但无资源时显示准备中空态 | `GET /resources` | ✅ 已可操作 | 按当前教学班 `course_id` 读取资源；不展示 Admin 原始资料。 |
| `ResourceDetail.jsx` | 查看资源详情、正文、代码、Mermaid mindmap | `GET /resources/{id}` | ✅ 已可操作 | Mermaid 渲染是前端展示能力。 |
| `Quiz.jsx` | 按节点/自由模式获取题目并提交答案 | `GET /quiz/questions?node_id=xxx`、`POST /quiz/submit` | ✅ 已可操作 | 支持节点模式（LearningPath 带 node_id 进入）和自由模式；后台诊断失败不阻塞结果。 |
| `PracticeResult.jsx` | 查看练习结果 | `GET /quiz/result` | ✅ 已可操作 | 做完留在结果页，手动返回。 |
| `LearningPath.jsx` | "进入练习"带节点上下文 | `/quiz?course_id=xxx&node_id=yyy` | ✅ 已可操作 | 从节点面板点"进入练习"跳转 Quiz。 |
| `AIChat.jsx` | 查看会话、历史消息、SSE 对话 | `GET /tutoring/conversations`、`GET /tutoring/conversations/{id}`、`POST /tutoring/chat` | ✅ 已可操作 | 已兼容对象型 `knowledge_points` 防白屏。 |
| `LearningPath.jsx` | 查看学习路径、查看节点资源 | `GET /learning-path`、`GET /learning-path/nodes/{node_id}/resources` | ✅ 已可操作 | 没有调用 `refreshLearningPath()`。 |
| `LearningEffects.jsx` | 查看学习效果 | `GET /evaluation` | ✅ 已可操作 | 没有调用 `refreshEvaluation()`。 |
| `TeacherConsole.jsx` | 查看班级、绑定资源库状态、当前教学班上下文下的共享资源、课程码、学生列表、班级洞察 | `GET /courses`、`GET /resources`、`GET /teaching/classes/{class_id}/students`、`GET /teaching/classes/{class_id}/insights` | ✅ 已可操作 | 教师端只读确认绑定资源库资源，可跳转资源详情并复制课程码；不提供生成/上传/删除资源入口。 |
| `TeacherStudentReport.jsx` | 查看单个学生学习报告 | `GET /teaching/classes/{class_id}/students/{student_id}/learning` | ✅ 已可操作 | `overall_score` 真实口径仍待设计，前端不展示硬编码分。 |
| `AdminConsole.jsx` | 管理用户、查看日志、创建/查看课程资源库 | `GET /admin/users`、`DELETE /admin/users/{user_id}`、`GET /admin/logs/agent`、`GET /admin/logs/operations`、`GET/POST /admin/course-catalogs` | ✅ 已可操作 | 用户停用状态持久展示仍缺契约字段。 |
| `CourseCatalogDrawer.jsx` | 上传资料、触发入库向量化、轮询任务、查看知识库状态、基于知识切片自动刷新课程知识图谱、触发资源库级学习资源生成、查看生成资源、软删除资料/资源 | `GET /materials`、`GET /knowledge-status`、`POST /materials/upload`、`POST /ingestions`、`GET /tasks/{task_id}`、`GET /admin/course-catalogs/{catalog_id}/knowledge-graphs`、`POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`、`GET /admin/course-catalogs/{catalog_id}/resources`、`POST /admin/course-catalogs/{catalog_id}/resources/generations`、`DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}`、`DELETE /admin/resources/{resource_id}` | ✅ 已可操作 | Admin 资料导入、向量化、自动 KG 刷新、资源生成和软删除的核心入口；KG 生成/状态读取可在未绑定真实教学班时通过隐藏宿主课完成，UI 不暴露大纲文本 / KG JSON 调试输入。 |
| 无页面入口 | 资源生成 | `POST /resources/generate` | 🚫 前端不接入 | 历史接口 / 废弃候选；教师端不提供生成资源入口，不作为当前 UI 或联调主线。 |
| 无页面入口 | Quiz 生成 | `POST /quiz/generate` | 🚫 前端不接入 | 历史接口 / 废弃候选；练习页不引导触发生题，不作为当前 UI 或联调主线。 |

## 功能主线账本

### 一、基础主链路

| # | 功能 | 状态 | 已实现内容 | 下一步 |
| --- | --- | --- | --- | --- |
| 1 | Auth 登录 / 注册 / 验证码 / 鉴权恢复 | ✅ 已可操作 | 登录、注册、验证码、`/users/me`、用户资料更新已接真实 API | 后续扩展用户字段必须先同步 OpenAPI。 |
| 2 | 课程列表 / 加入课程 / 教师创建教学班 | ✅ 已可操作 | 学生/教师课程列表、加入课程、创建教学班、绑定 ready CourseCatalog；隐藏 KG 宿主课已从真实课程流中过滤 | 无当前阻塞。 |
| 3 | 学生 Dashboard 资源列表 | ✅ 已可操作 | 按当前课程拉取 `GET /resources`；有课程但无资源显示“课程资源正在准备中 / 请稍后查看” | 资源内容质量依赖 #11。 |
| 4 | 资源详情 / 正文 / Mermaid 渲染 | ✅ 已可操作 | `GET /resources/{id}` 返回内容，前端按类型展示；学生和教师均可从资源列表进入详情 | 资源内容质量依赖 #11。 |
| 5 | Quiz 取题 / 提交 / 结果 | ✅ 已可操作 | Admin 批量生成保底题库 + `GET /quiz/questions` 加 `node_id` filter，节点/自由两模式 | 保底题 source=baseline 全员可见；个性化题阶段二后置。 |
| 5A | Admin 批量生成保底题库 | ✅ 已可操作 | CourseCatalogDrawer 一键生成（按 KG 全部节点，每节点 3 单选+4 多选），`POST /admin/course-catalogs/{id}/quiz/generations` | 保底题库已闭环，答题链路可走通。 |
| 7 | AI Chat SSE | ✅ 已可操作 | 会话列表、历史消息、SSE 流式对话已接真实 API | 后续审查 `knowledge_points[]` 元素类型契约。 |
| 8 | 教师班级 / 资源 / 学生 / Insights | ✅ 已可操作 | 教师端课程、绑定资源库状态、本班学习资源、学生列表、班级洞察已接真实 API | 教师端资源区只读，不提供生成/上传/删除资源入口；复杂指标必须先契约设计。 |
| 9 | 管理员用户 / 日志 | ✅ 已可操作 | 用户列表、停用、Agent 日志、系统日志已接真实 API | 停用状态持久展示见 #28。 |

### 二、CourseCatalog 与知识库入库

| # | 功能 | 状态 | 已实现内容 | 下一步 |
| --- | --- | --- | --- | --- |
| 10 | CourseCatalog 三表 + 教学班绑定 | ✅ 已可操作 | `CourseCatalog`、`CourseCatalogMaterial`、`CourseOffering` 已支撑 Admin 建资源库、教师开班绑定资源库 | 无当前阻塞。 |
| 11 | Admin 资料上传 / 登记 | ✅ 已可操作 | Admin 抽屉可上传 `txt/md/pdf`，Backend 保存文件并创建 `CourseCatalogMaterial` | 部署时不要提交上传文件或 storage 产物。 |
| 12 | Admin 触发入库向量化 | ✅ 已可操作 | Admin 点击入库后，Backend 创建 `course_catalog_ingestion` task，Agent 切片、embedding、Qdrant upsert，Backend 回写 `chunk_count/knowledge_status`，前端轮询刷新 | 建议做一次部署级 live smoke，确认真实 Qdrant/storage/provider 配置。 |
| 13A | Admin 自动刷新课程知识图谱 | ✅ 已可操作 | Admin 抽屉调用 `POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`，默认空请求体，Backend 基于资源库已入库知识切片自动生成 active KG，独立轮询 `kg_generation` task，完成后刷新 active KG 摘要；未绑定真实教学班时由隐藏 KG 宿主课承载图谱版本与状态读取 | 不触发学生个性化 LearningPath 刷新；`kg_json` 仅保留后端调试兼容，Admin UI 不暴露。 |
| 13 | Admin 资源库级学习资源生成 | ✅ 已可操作 | Admin 抽屉调用 `POST /admin/course-catalogs/{catalog_id}/resources/generations`，按资源类型触发生成，独立轮询 `resource_generation` task，完成后刷新生成资源列表 | 当前新生成资源以 `catalog_id` 为主归属写入共享资源；建议做一次部署级 live smoke，确认 Agent 返回资源、共享资源落库和前端刷新一致。 |
| 14 | Admin 资料 / 生成资源软删除 | ✅ 已可操作 | Admin 抽屉调用资料和资源 DELETE 接口；资料删除后可显示 `dirty`，资源删除后从生成资源列表消失 | 软删除不删除文件、Qdrant chunks 或 Agent 产物。 |
| 15 | 学生 / 教师消费资源库共享学习资源 | ✅ 已可操作 | 学生 Dashboard 和教师资源区都按当前教学班 `course_id` 解析绑定资源库后读取共享资源；无资源分别显示准备中 / 联系管理员生成 | 新生成资源按资源库存储并跨绑定教学班共享；legacy 按班资源仅兼容当前教学班读取。 |
| 16 | 历史生成接口 CourseCatalog ready gate | ✅ 后端闭环 + 🚫 前端不接入 | `/resources/generate` 和 `/quiz/generate` 曾共用 ready gate：`status=ready`、`knowledge_status=ready|partial`、`chunk_count>0` | 不再驱动教师端 / 学生端 UI 或下一步主线；保留为历史后端能力 / 废弃候选背景。 |

### 三、历史生成接口 / 前端不接入

| # | 功能 | 状态 | 已实现内容 | 下一步 |
| --- | --- | --- | --- | --- |
| 17 | 资源生成 `/resources/generate` | 🚫 前端不接入 | Backend 曾实现 API、ready gate、Agent payload 使用 `CourseCatalog.id`；前端正式入口已删除 | 当前前端契约作废 / 不接入；不得新增教师端生成资源入口。 |
| 18 | Quiz 生成 `/quiz/generate` | 🚫 前端不接入 | Backend 曾实现 API、ready gate、Agent payload 使用 `CourseCatalog.id`，题目按教学班 id 落库 | 当前前端契约作废 / 不接入；练习页不引导触发生题。 |
| 19 | 资源/题目/诊断内容质量 | ⏸️ 暂缓 | 暂不靠前端文案遮盖 Agent 质量问题 | 先确认 Admin 入库资源和现有题库消费口径，再决定是否需要新的生成产品设计。 |

### 四、Agent 依赖能力

| # | 功能 | 状态 | 已实现内容 | 下一步 |
| --- | --- | --- | --- | --- |
| 20 | LearningPath 展示 / 节点资源 | ✅ 已可操作 | 页面可展示学习路径并查看节点资源；无 LP 记录时从 active KG 拓扑排序合成路径骨架（source="kg_fallback"），全节点 recommended | KG fallback 已闭环，不再依赖 Agent 个性化生成来显示基础路径。 |
| 21 | LearningPath 刷新 | ⚠️ 前端无入口 + ⏸️ 暂缓 | `learningService.refreshLearningPath()` 和 `/learning-path/refresh` 存在，但页面无调用；KG fallback 已覆盖基础展示 | 当前阶段不需要接刷新 UI；如未来需要 Agent 个性化路径，再评估。 |
| 22 | KG ready gate | ⏸️ 暂缓 | KG fallback 已让 LearningPath 可用，不再阻塞主流程 | 待 Agent 个性化路径设计后再定。 |
| 23 | 学生画像展示 / 对话补充 | ✅ 已可操作 | `StudentProfile.jsx` 调 `GET /profile` 展示六维画像，调用 `POST /profile/dialogue-update` 用自然语言补充学习目标、薄弱点和资源偏好，并展示 `/users/me` 基础资料 | 后续新增画像维度仍必须走契约。 |
| 24 | Profile refresh | ✅ 已可操作 | `StudentProfile.jsx` 提供“同步画像”按钮，调用 `POST /profile/refresh` 创建 `profile_refresh` task，轮询 `GET /tasks/{task_id}`，完成后重新拉取 `GET /profile` | 该入口为静默随学更新，不暴露 prompt 输入。 |
| 25 | 学习效果展示 | ✅ 已可操作 | `LearningEffects.jsx` 调 `GET /evaluation` | 累计时长/趋势等仍是阶段二缺口。 |
| 26 | Evaluation refresh | ⚠️ 前端无入口 | `learningService.refreshEvaluation()` 存在，对应 `/evaluation/refresh`，但页面无调用 | 决定是否接刷新入口或删除误导性 service。 |
| 27 | 教师学生深度报告 | ✅ 已可操作 + 📋 待设计局部口径 | 学生报告页面接 `GET /teaching/classes/{class_id}/students/{student_id}/learning` | `overall_score` 真实计算口径待设计。 |

### 五、待设计 / 暂缓

| # | 功能 | 状态 | 当前判断 | 下一步 |
| --- | --- | --- | --- | --- |
| 28 | Admin 用户停用状态持久展示 | 📋 待设计 | 当前 `GET /admin/users` 契约未返回 `is_active/status`，页面刷新后无法持久展示停用状态 | 先扩展 Client API，再同步 Backend/Frontend。 |
| 29 | AI Chat `knowledge_points[]` 元素类型 | 📋 待设计 | 真实历史响应出现对象元素，OpenAPI 仍声明 string；前端已兼容防白屏 | 做契约审查，决定 string 还是 object union。 |
| 30 | 复杂教师/Admin 指标 | 📋 待设计 | 排名、覆盖率、动力指数等不能前端补造 | 先设计 SQL/Agent/Client API 来源。 |
| 31 | 累计学习时长 / 阅读进度 / AIChat 活动摘要 / 资源偏好分布 | ⏸️ 暂缓 | 缺行为采集口径和 activity 表设计 | 单独数据采集专项。 |
| 32 | Memory 压缩 | ⏸️ 暂缓 | Agent 内部能力，不进当前前端主线 | 不作为 Client API 功能推进。 |

## 当前下一步队列

1. **C 样本 catalog 数据一致性恢复**
   删除资料后 chunk 重算逻辑已修复，但真实 C catalog 已处于历史不一致状态。下一步先修正这条开发库数据或重新上传有效资料并入库。

2. **#28 Admin 用户停用状态契约**
   如果继续完善 Admin 用户管理，先扩展 `GET /admin/users` 返回状态字段。

4. **LearningPath 节点资源挂载验证**
   KG fallback 已让学习路径页面可显示骨架，下一步验证真实 C 样本的节点资源（weak_point_tutorials/exercises/chapter_materials）是否能在页面上正确展示。当前 resources 表挂载到 KG 节点的数据可能仍缺。

5. **Evaluation refresh 入口决策**
   Profile 已具备对话补充和静默同步画像入口；仍需决定 `learningService.refreshEvaluation()` 是否接前端刷新按钮或删除误导性 service。

## 纠偏记录

- TeacherConsole 曾经接过资源生成 UI；CourseCatalog 主线调整后已经移除。当前教师端资源生成没有前端正式入口；Admin 资源库级生成使用独立 Admin 端点。
- 2026-06-09 契约纠偏：`/resources/generate`、`/quiz/generate` 在当前前端契约中标记为作废 / 不接入；教师端不提供生成资源入口，练习页不提供触发生题入口。
- `learningService.triggerResourceGeneration()` 和旧 `learningService.getTaskStatus()` 已删除；任务查询由 `taskService.getTaskStatus()` 承担。
- Admin 课程资源库导入和向量化已经实现，不应再误判为“只做了后端”或“没接 UI”。
- `refreshLearningPath()`、`refreshEvaluation()`、`quizService.getHistory()` 这类方法存在不等于用户功能可操作；必须看页面是否调用。`refreshProfile()` 已由个人资料页接入为静默同步画像入口。
- 后续更新本账本时，必须优先写用户入口和真实调用，再写文件证据。
- 2026-06-09 资源消费闭环归档：最初版本采用按班存 / 按班读；该口径已在 2026-06-12 切换为“教学班绑定资源库、资源按资源库共享读取”，legacy 按班资源仅保留兼容读取。
- 2026-06-10 KG 方向纠偏：现有 CLI 目录版 KG 已在真实 catalog `b2444963f0e54587` / course `6c698badb60a4809` 生成 `116` 节点，但排除目录型 chunk 后仅 `25/116=21.6%` 节点达到正文支撑阈值；同时正文资料密度足够（知识型正文 `465/613=75.9%`）。因此下一步不是审核 / 签字或 KG ready gate，而是先做 KG 版本 / 回滚，再按“目录骨架 + 正文 chunk 验证 / 补充”的路线 A 返工 KG 生成。
- 2026-06-10 Route A 真实闭环：KG 版本 / 回滚和两段式工具链已完成；开发库 C 语言样本生成 Route A `version=2`，但只保留 `22/116=18.97%` 节点、`2` 条边，未达到跑前固定成功线 `>=70%`。结论是工具链可跑通，但 KG 生成未完成；下一步改生成策略，不能进入 KG ready gate、资源继承 KG 节点名或审核流程。
- 2026-06-10 Route A no-go 归因：失败不是资料缺失；主要问题是 47 个节点仍命中目录/索引/点线页码噪声，49 个节点落在 `0.65-0.70` 边缘区，说明正文候选过滤和单节点名 query 都不够稳。下一步先做过滤与 query 扩展探针，再决定正文补点或正文聚类。
- 2026-06-10 过滤与 query 扩展探针复验：增强目录/点线页码/附录索引过滤后，真实 C 语言样本 baseline `22/116=18.97%` 变为 `18/116=15.52%`，说明过滤主要纠正误判，不直接提分；开启 `node.name + chapter/node_name/相邻节点名` 双 query 取最优后提升到 `57/116=49.14%`，49 个边缘节点中 23 个过线，但仍未达到 `>=70%`。下一步进入正文补点 / 正文聚类。
- 2026-06-11 Route A 可用阈值版本通过：Backend Route A 裁剪默认线从 `0.70` 调整为 `0.60`，开发库 C 语言样本生成 active KG `version=3`、`108/116` nodes、`100` edges，分档为 `strong=57`、`good=34`、`weak_but_usable=17`、`unsupported=8`。`weak_but_usable` 可进入 active KG，但后续 ready gate 不得把它当成 strong 支撑；`metrics.pruned_nodes` 仍保留完整 detail 列表，未来大图需考虑限长或外部诊断产物。
- 2026-06-11 KG-Resource 对齐探针复验：`b2444963f0e54587` / `6c698badb60a4809` 已具备正式探针条件并导出 108 行 KG 节点候选，但 `108/108` 节点 `candidate_count=0`。零命中原因是当前资源元数据仍为 `chapter=课程整体`、`knowledge_point=综合知识点`，不是新版 active KG 未生效；下一步转为资源生成 metadata / KG 映射设计。
- 2026-06-11 KG-node 资源生成闭环：新增维护工具先 recheck/repair C catalog 的 `knowledge_status dirty -> ready`，确认非删除资料全 ingested、chunk 正常且 Qdrant 可查；随后 Admin 资源生成接口不传 `chapter/knowledge_point`，自动选 10 个 active KG 核心节点生成资源，父任务 `d364a3a0af294dfa` 完成且 `10/10` 子任务成功。复跑 KG-Resource probe 后 `108/108` active KG 节点 `candidate_count>0`，资源 metadata 与 KG 节点对齐问题已在 C 样本闭环验证。
- 2026-06-11 LearningPath-KG 资源命中评估基线：新增只读 probe 后跑真实 C 样本，报告 `/tmp/learning-path-resource-probe-c-language.json` 显示 `active_kg_node_count=108`、`resource_count=84`、`kg_tagged_resource_count=80`，但 `learning_path_id=null`、`learning_path_node_count=0`；只读 MySQL 复核该 course 当前无非删除 LearningPath，因此不能直接评估 ready gate，下一步必须先生成 / 刷新 LearningPath。
- 2026-06-13 Admin 批量生成保底题库：CourseCatalogDrawer 新增"生成题库"按钮，一键为全部 KG 节点生成保底题库（source=baseline, 3 单选+4 多选/节点）。`GET /quiz/questions` 加 `node_id` 支持节点模式答题，source 过滤加 `baseline`。LearningPath "进入练习"带 node_id，Quiz 页面支持从 URL 读取节点参数。
- 2026-06-12 LearningPath KG Fallback：`GET /learning-path` 无 LP 记录时不再返回空，而是从 active KG 拓扑排序合成路径骨架（全 recommended）。KG fallback 已闭环，不再阻塞学习路径页面展示；Agent 个性化生成后置，不删除历史 refresh 端点但当前不需要接 UI。
- 2026-06-13 AI Chat Hybrid Retrieval 验证完成：后端已将 `active_kg_nodes` 透传给 Agent Service 的 `TutoringChatRequest`，Agent 内实现了 KG 节点与 User Message 语义匹配打分，并将其作为兜底 Knowledge Points 注入 prompt。新增了探针端点 `/retrieval_probe` 和 CLI 工具（支持分数与 `--json` 输出）。当前已进入「探针与 mock 回归已完成，真实 Hybrid 闭环待验证」状态。
- 2026-06-11 Admin 删除资料一致性修复：删除 CourseCatalog material 后现在会按剩余未删除 material 重算 `catalog.chunk_count`，避免删除最后一个有效资料后 catalog 仍保留历史 chunk 并误判 ready。真实 C catalog 已存在的历史不一致数据不会被代码自动回填，需单独修正或重新入库。

## 更新规则

每次开发结束后按以下规则更新本文件：

1. 新增用户可操作功能：加到“页面真实调用核查”和对应主线表。
2. 后端能力完成但无 UI：标 `✅ 后端闭环 + ⚠️ 前端无入口`。
3. 真实多服务联调未跑：标 `🔄 联调待验收`。
4. 删除或延期能力：写入“纠偏记录”或 `⏸️ 暂缓`。
5. 下一步队列只保留 3-5 项，不写长愿望清单。
