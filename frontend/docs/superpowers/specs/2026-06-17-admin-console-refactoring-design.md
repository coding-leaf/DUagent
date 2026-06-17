# AdminConsole 视图解耦与组件拆分设计 (Option 2)

## 背景
根据 Phase 2 Master Plan 的 Direction 1（整理目录，消除大文件），当前 `src/pages/AdminConsole.jsx` 达 39KB（约 800 行代码）。它违背了单一职责原则，将四个完全独立的业务领域（用户管理、课程资源库、系统日志、注册码管理）的状态和 DOM 混杂在同一个组件中。这导致其不仅难以维护，且容易引发不必要的全局重新渲染。

## 架构选型与设计模式
- **视图拆分 (View Splitting)**：基于业务域将代码进行纵向切片。主页面只负责 Layout 与 Tab 导航。
- **高内聚低耦合 (MVVM 局部化)**：摒弃全局大 Hook 的想法。将各自的数据状态（State）与数据请求（Service Call）完全下沉到其对应的领域组件内部，实现自治。

## 设计细节

1. **核心文件与目录规划**
   新建以下 4 个业务组件存放在 `src/components/admin/` 目录下：
   - `UserManagementPanel.jsx`：承载用户列表、搜索、停用与密码重置逻辑。
   - `CatalogManagementPanel.jsx`：承载课程库列表、创建新资源库逻辑（内部直接挂载 `CourseCatalogDrawer`）。
   - `SystemLogsPanel.jsx`：承载系统日志、Agent日志查看及切换。
   - `RegistrationCodesPanel.jsx`：承载生成与吊销注册码逻辑。

2. **状态与网络请求下沉**
   - 现有的 `fetchUsers`, `fetchLogs`, `fetchCatalogs`, `fetchRegCodes` 以及它们关联的 state（如 `users`, `catalogs`, `agentLogs` 等）将全部从 `AdminConsole.jsx` 中剪切，直接粘贴到对应的 Panel 组件内。
   - 每个 Panel 组件自己负责 `useEffect` 初始化数据。
   - **错误处理升级**：由于前置任务（Option 1）已完成了全局拦截器，在下沉代码时，应当顺手清理掉之前残留的冗余 `catch (e) { setError(...) }` 样板代码，或只保留确实需要局部显示的 UI 状态。

3. **主容器 (`AdminConsole.jsx`) 的瘦身**
   - 主文件仅保留 Layout（Navbar、Sidebar）和 `activeTab` 状态。
   - 通过按需渲染对应的 Panel 组件，文件行数预期缩减至 100 行以内。
