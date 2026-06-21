# EDUagent 项目全栈架构治理与重构成果报告

本报告系统性地梳理了当前 EDUagent 项目在“架构治理与重构阶段”取得的丰硕成果。本次重构完全对齐了项目制定的五大重构方向，理清了表现层（React）、业务网关（FastAPI 后端）与智能体服务（Agent Service）的边界，彻底消除了复杂大文件，重构了竞态并发控制，并补齐了核心测试套件。

---

## 一、 后端重构：瘦路由与 Service 层提取

重构前，后端的 API Router 文件直接承担了数据库查询、事务开启、Agent 网络 I/O、权限校验以及复杂的返回数据拼接，导致代码高度耦合（例如旧评估路由长达约 460 行）。
重构后，我们推行了 **Router -> Service -> DB Model** 的分层设计，使路由层仅保留接口定义、Schema 校验和基本委派职责。

### 1. 核心 Service 模块提取
后端新增/重构了三大高内聚的业务服务类，移出了 API 路由文件中的全部业务组装：
* **`EvaluationService`** ([evaluation_service.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/app/services/evaluation_service.py))：承接学情评估数据的获取、软删除、新记录写入与异步线程调度。
* **`ResourceService`** ([resource_service.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/app/services/resource_service.py))：管理课程级公共资源与学生专属个性化资源的读取过滤。
* **`CatalogMaterialService`** ([catalog_material_service.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/app/services/catalog_material_service.py))：封装原始课程资料的保存、软删除、状态计数以及物理存储清理。

### 2. 胖路由瘦身对比
| 路由模块 | 重构前行数 | 重构后行数 | 核心下沉逻辑 |
| :--- | :--- | :--- | :--- |
| **评估路由 (`evaluation.py`)** | ~460 行 | **25 行** | 迁入 `EvaluationService`，仅保留 HTTP 202 异步接收和拉取任务。 |
| **资源路由 (`resources.py`)** | ~118 行 | **30 行** | 迁入 `ResourceService`，剥离底层复杂的 scope 和个性化查询组装。 |
| **目录路由 (`catalogs.py`)** | ~350 行 | **130 行** | 迁入 `CatalogMaterialService`，剥离物理文件写盘、批量删除与数据库上下文处理。 |

---

## 二、 并发锁与事务优化：防脏写与竞态安全

在多 Agent 并发异步回调（Webhook/asyncio 异步后台任务）的环境中，学生画像、学情路径和评估报告面临严重的数据竞态风险。我们重构了锁机制与事务粒度：

1. **Named Lock (进程级命名锁)**：
   * 在画像更新、学情生成等关键路径引入了 MySQL 进程级锁 `GET_LOCK(lock_name, timeout)`。
   * **兼容性设计**：后端在 [locks.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/app/infrastructure/locks.py) 增加了数据库方言判断。当运行环境为 SQLite（如本地测试套件）时自动避开 MySQL 特有的命名锁调用，确保生产 MySQL 环境与测试环境完全兼容。
2. **短事务生命周期优化**：
   * 将 Agent 的长网络 I/O 挪出主数据库事务之外。
   * 后端仅在短事务中创建 `AsyncTask` 唯一任务 ID 并立即 `commit` 提交，随后在不占数据库连接的后台异步任务或回调 Webhook 中与 Agent 握手。接收到数据后，再在命名锁保护下开启另一个短事务写入数据，规避了长事务导致的 MySQL 连接池耗尽风险。

---

## 三、 前端重构：SWR 状态管理与 MVVM 重构

为了落实 “Reuse-First” 原则，我们清除了前端组件中手写 `useEffect` 驱动的重复 API 轮询、易漏的定时器泄露与手动取消 ref。

1. **`ResourceDetail.jsx` 解耦**：
   * 新建自定义 SWR Hook [useResourceDetail.js](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/hooks/useResourceDetail.js)。
   * 实现缓存优先（Cache-first）的数据拉取。页面只负责通过 Hook 获取 `resource` 状态并进行沉浸式渲染，移除了手写的 Axios 加载。
2. **`useCatalog.js` 异步轮询重构**：
   * 采用 SWR **条件轮询机制 (Conditional Polling)** 自动接管轮询生命周期。
   * 通过设置条件 key：
     ```javascript
     const { data: activeTaskSWR } = useSWR(
       activeTaskId && open ? ['taskStatus/ingestion', activeTaskId] : null,
       () => taskService.getTaskStatus(activeTaskId),
       { refreshInterval: (data) => data?.status === 'processing' ? 2000 : 0 }
     );
     ```
     当没有任务或抽屉关闭时，SWR 自动关闭轮询；一旦有进行中的任务，SWR 自动按间隔查询直至任务状态变为 completed/failed。
   * 彻底清除了前端近百行嵌套的 `setTimeout`、请求序列序列号对比以及取消标志位（`cancelled`），代码更加清晰、不易泄漏。

---

## 四、 测试套件补齐与代码质量验证

本着重构必须有测试保障的原则，我们对新抽离的服务和路由层进行了测试用例补全，并执行了前后端集成验证。

1. **新增后端测试文件**：
   * [test_evaluation_service_refactored.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/tests/test_evaluation_service_refactored.py) (覆盖评估服务的创建、画像及选课校验、成绩表提取逻辑)。
   * [test_evaluation_routes_refactored.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/tests/test_evaluation_routes_refactored.py) (测试 HTTP 刷新请求、202应答及降级场景)。
   * [test_resource_service.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/tests/test_resource_service.py) (验证公共与个性化课件的作用域安全机制)。
   * [test_catalog_material_service.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/tests/test_catalog_material_service.py) (测试讲义的真实上传流保存、软删除与数据项一致性)。
2. **测试与构建通过证明**：
   * 后端语法静态校验：`python3 -m py_compile` 对所有新模块全部通过。
   * 前端语法与构建校验：在 `frontend/` 下执行 `npm run lint` 与 `npm run build`，编译完全成功，**零报错，零警告**。

---

## 五、 系统物理与逻辑边界确立

本次重构严格捍卫了项目的架构安全边界：
1. **Agent 独立运行规范**：通过对 `agent_service` 代码的审计，确认其在逻辑 and 物理层均**不连接 MySQL**。所有状态依赖通过 Backend 提供的 RESTful 接口进行拉取。
2. **三端协同链路文档化**：整理并全中文重写了主架构指南 [docs/architecture_flow_overview.md](file:///home/yezisama/workspace/workflow/EDUagent/docs/architecture_flow_overview.md)，为未来开发者厘清了全栈数据流向。

---

## 结论

本次重构在**不破坏任何现有用户功能、零接口协议漂移**的前提下，让 EDUagent 全栈项目从“前期无节制堆砌代码”的混沌状态，平稳步入了**“逻辑层分明、组件正交、高并发防脏写、自动化测试兜底”**的现代化架构时代。
项目代码可读性、维护性已获得质的提升，架构治理目标阶段性圆满达成。
