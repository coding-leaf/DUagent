# EDUagent Project Direction

本文档用于在开发断层后快速恢复项目上下文，长期指导后续开发方向。它不替代接口契约、执行计划或进度记录，只回答三个问题：

1. 当前项目按什么结构理解。
2. 后续开发按什么方向推进。
3. 断层后如何重新判断下一步。

## 文档定位

权威来源按以下顺序读取：

1. `../docs/10-client-api/Client-API.openapi.json`
2. `../docs/10-client-api/API_前端接口规范.md`
3. `../docs/20-agent-api/Agent-Service.openapi.json`
4. `AGENTS.md`
5. `WORKFLOW.md`
6. `docs/goals.md`
7. `docs/decisions.md`
8. `docs/glossary.md`
9. `docs/superpowers/specs/`
10. `docs/superpowers/plans/`

使用原则：

- OpenAPI 和接口规范决定前后端正式契约。
- `AGENTS.md` 决定本工作区协作、修改、测试和提交规则。
- `WORKFLOW.md` 只记录当前进度和最近验证。
- `docs/superpowers/specs/` 记录已确认设计。
- `docs/superpowers/plans/` 记录可执行实施计划。
- 归档、草案、页面设想和 mock 数据不能直接作为实现依据。

## 项目结构

项目是三层协作系统：

- `frontend/`：React + Vite 浏览器应用，只调用 Backend Client API。
- `backend/`：FastAPI Client API、数据库模型、业务编排、异步任务和 Agent Service 调用。
- `agent_service/`：Agent 内部 API、知识库入库、资源生成、题目生成、诊断和学习路径相关能力。

核心数据方向：

```text
Frontend -> Backend Client API -> SQL / AsyncTask / Agent Service -> Backend webhook or response -> Frontend polling/display
```

边界：

- Frontend 不直接调用 Agent Service。
- Frontend 不直接访问 SQL、Qdrant 或本地存储。
- Backend 是 Client API 和 Agent API 的边界层。
- Agent Service 不决定前端页面契约。

## 当前已收口主线

已完成并进入基线的能力：

- 阶段一真实 Backend 主链路：登录、注册、课程、资源列表、学习路径基础展示、Quiz、AI Chat、教师基础学情、管理员基础页面。
- 阶段二部分契约对齐：ResourceDetail 内容、LearningPath 节点资源、教师端学生聚合、AdminConsole 既有契约对齐。
- CourseCatalog 三表和教学班绑定：`CourseCatalog`、`CourseCatalogMaterial`、`CourseOffering`。
- 课程资源库资料入库编排：Backend 创建入库任务，Agent Service 执行 ingestion，Backend 回写状态。
- Admin 课程资源库入库 UI：上传资料、触发入库、查看知识库状态、轮询任务。
- 资源生成和 Quiz 生成前置 CourseCatalog ready gate：生成前解析教学班绑定的 `CourseCatalog`，校验 `status`、`knowledge_status` 和 `chunk_count`。

当前 ready gate 口径：

- 可用：`status=ready` 且 `knowledge_status=ready|partial` 且 `chunk_count>0`。
- `partial` 可用但视为降级状态，`degraded=true`。
- 不可用：`draft`、`dirty`、`ingesting`、`failed`、非 ready catalog、零 chunks、未绑定 CourseCatalog。

当前错误码：

- `404 course_catalog_missing`
- `409 course_material_missing`
- `409 knowledge_base_empty`

## 当前方向

下一阶段不要继续盲目补页面字段。优先方向是让真实数据链路稳定闭环：

1. 真实 Backend + Agent Service 联调资源生成。
   - 验证 `/resources/generate` 使用 catalog id 调 Agent。
   - 验证 Agent webhook 回写资源。
   - 验证前端资源列表和详情能看到真实生成内容。

2. 真实 Backend + Agent Service 联调 Quiz 生成。
   - 验证 `/quiz/generate` 使用 catalog id 调 Agent。
   - 验证 Backend 仍按教学班 id 持久化题目。
   - 验证个性化上下文仍按教学班 id 查询。

3. 设计 LearningPath / KG ready 口径。
   - LearningPath 依赖 KG，不应直接复用 chunk-only ready gate。
   - 需要单独确认 KG 状态、错误码、降级策略和前端提示。

4. 收口真实数据质量。
   - 资源内容质量、题目质量、诊断质量应进入独立专项。
   - 不用前端文案或 mock 遮盖 Agent 产出问题。

5. 再推进阶段二剩余页面能力。
   - 累计学习时长、阅读进度、AIChat 活动摘要、资源偏好分布等，需要先明确采集口径和数据表。
   - Teacher / Admin 更复杂统计也必须先完成契约设计。

## 禁止事项

除非已有明确设计和契约，不要做以下事情：

- 前端新增假字段、假统计、假图表。
- 为了页面好看硬编码 mock 数据到真实模式。
- 前端绕过 Backend 直连 Agent Service。
- Backend 为了某个页面临时返回未登记到 OpenAPI 的字段。
- 资源生成、Quiz 生成、LearningPath 生成在资料缺失时静默泛化生成。
- 把 `docs/archive/` 或历史草案当作当前契约。
- 未经确认直接修改 `.env`、数据库文件、Qdrant 存储、MySQL volume、上传文件或构建产物。

## 断层恢复流程

每次上下文丢失后，先按这个顺序恢复事实：

1. 查看 `git status --short`，区分已跟踪改动和未跟踪文件。
2. 查看最近提交：`git log --oneline -10`。
3. 阅读 `WORKFLOW.md` 的“最近验证”和“下一步建议”。
4. 阅读当前任务对应的最新 spec 和 plan。
5. 对照代码现状，不把上一轮记忆当作事实。
6. 如果文档和代码冲突，先写清冲突点，不直接改。
7. 先收口未提交批次，再开新任务。

## 新任务执行顺序

每个新任务按以下顺序推进：

1. 明确任务属于哪个边界：Frontend、Backend、Agent Service、OpenAPI、测试、文档。
2. 查权威文档和代码现状。
3. 如果是新能力或行为变化，先写 design spec。
4. spec 确认后写 implementation plan。
5. 修改代码前按 `AGENTS.md` 输出审查内容。
6. 先补测试，再实现。
7. 运行最小相关测试，再运行必要的集成检查。
8. 同步 OpenAPI、前端调用、Backend schema/service、测试和 `WORKFLOW.md`。
9. 每个已确认小批次单独 git commit。
10. 最终总结必须写清状态、文件、测试、契约漂移、commit、风险和下一步。

## 判断下一步的规则

优先级从高到低：

1. 修复阻断真实主链路的问题。
2. 收口已设计但未完成的契约同步。
3. 补齐缺失测试或防止回归的 E2E。
4. 推进真实 Backend + Agent Service 联调。
5. 设计下一阶段能力。
6. 优化 UI 和文案。

如果出现多个候选任务，优先选择能让真实数据闭环更稳定的任务。

## 当前推荐下一步

推荐从“真实资源生成联调”开始，而不是新增页面：

1. 启动 Backend、Agent Service、MySQL 和必要的向量/存储依赖。
2. 用 ready 或 partial 的 CourseCatalog 触发资源生成。
3. 验证 Agent 使用 catalog id 检索知识库。
4. 验证 Backend webhook 创建 `resources`。
5. 验证教师端资源列表刷新和 ResourceDetail 正文展示。
6. 把失败点落成测试或 smoke 脚本。

完成资源生成真实闭环后，再用同样方式验证 Quiz 生成真实闭环。
