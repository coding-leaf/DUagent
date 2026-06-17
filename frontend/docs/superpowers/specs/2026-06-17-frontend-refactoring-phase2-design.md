# Frontend Phase 2 Refactoring Design (try-catch, TeacherConsole, StudentProfile)

## 1. 架构选型与依据 (Architecture Selection & Justification)

根据 `Phase 2 Master Plan` 附录中的系统架构与设计模式指引，本次针对前端的三大重构目标选用以下架构模式：

### 1.1 `try-catch` 收尾清理
* **选用的设计模式**：**责任链模式 (Chain of Responsibility) + 代理模式 (Proxy)**
* **不选用**：单例模式 (Singleton) —— Axios 实例虽具有单例性质，但重点在于处理异常的“拦截链”。
* **选型依据**：我们在上一阶段已经通过 `client.js` (Proxy) 引入了 Axios 拦截器 (责任链)。网络层负责捕获 401、403、500 等异常并通过 Sonner 全局 Toast 提示。因此，各个独立 UI 组件内部不需要再次 `try-catch` 并设置局部的 `error` state。移除这些散落的捕获代码能让组件代码体积大幅缩减，回归到只关注“成功态渲染”的纯粹视图。

### 1.2 `TeacherConsole.jsx` 与 `StudentProfile.jsx` 重构
* **选用的系统架构**：**Container/Presentational Pattern + Custom Hook Pattern (Separation of Concerns)**
* **纠正说明**：原先提议的 MVVM 并不准确，React 的单向数据流生态下，更标准的称呼是容器与展示组件分离。
* **选型依据**：这两个组件目前是典型的“胖容器”。它们包含了拉取数据、状态流转、以及复杂的 DOM 渲染。我们将严格实施职责分离：
  - **逻辑复用层 (Custom Hook)**：提取 `useTeacherConsoleData()` 和 `useStudentProfile()` Hooks，负责管理所有异步请求、轮询逻辑。
  - **展示层 (Presentational Components)**：将庞大的 JSX 拆解为无状态 (Stateless) 的子组件 (例如 `ProfileHeader`, `RadarChart`, `ClassList` 等)。
  - **容器层 (Container)**：主 Page 组件仅负责调用 Hook 获取数据并向下传递 Props。

### 1.3 避免重复造轮子：引入辅助数据流框架
* **问题现状**：在 `StudentProfile` 中，存在手写的长轮询（Long Polling / `pollTask`）逻辑，代码冗长且容易出现内存泄漏、竞态条件等问题。
* **引入建议**：**SWR** 或 **React Query** (推荐轻量级的 `swr`)
* **选型依据**：使用 `swr` 可以彻底消除我们手写的轮询和缓存逻辑。例如，只需一行代码 `useSWR('/api/task', fetcher, { refreshInterval: 3000 })` 即可完美实现支持可见性聚焦、自动重试、缓存更新的工业级轮询逻辑。在本次重构开始前，我们将先执行 `npm install swr`，随后在 Custom Hook 中大面积替换掉脆弱的 `useEffect` 数据请求。

---

## 2. 详细重构规划 (Detailed Refactoring Plan)

### 任务 1：网络层 `try-catch` 清理 (Clean up global catch)
* **目标文件**：散布在 `src/pages/` 和 `src/components/` 中的遗留网络请求。
* **重构动作**：
  - 搜索所有直接包含 `console.error(e)` 和 `setError('xxx')` 的 `catch` 块（在 Axios 拦截器已经处理的范围内）。
  - 对于已经由 `client.js` 全局接管的常规查询接口，精简掉 `catch`，或者保留 `catch` 仅做 loading 状态复位，不再重复渲染局部的错误提示。

### 任务 2：重构 `TeacherConsole.jsx` (585行)
* **痛点**：教学班级管理、学生详情、平台资源三个正交的领域揉在一个页面，`useEffect` 数据流复杂。
* **重构动作**：
  - 提取 `useTeacherConsoleData.js` 处理数据拉取。
  - 拆分 `TeacherClassManager.jsx` (班级管理)。
  - 拆分 `TeacherStudentList.jsx` (学生列表)。
  - 主页面 `TeacherConsole.jsx` 缩减为 Layout 骨架。

### 任务 3：拆分 `StudentProfile.jsx` (909行)
* **痛点**：包含后台任务轮询、雷达图、学习路径图、能力模型、偏好设置，是目前最大的胖组件。
* **重构动作**：
  - 提取 `useStudentProfile.js` (含 `pollTask` 和数据拉取逻辑)。
  - 拆分子组件至 `src/components/profile/`：
    - `KnowledgeCoordinatesCard.jsx`
    - `ModalityPreferenceCard.jsx`
    - `LearningHabitsCard.jsx`
  - 主页面精简，仅做 Grid Layout 组合。

---
## 3. 测试覆盖 (Testing Strategy)
每次拆分一个页面后，必须在终端执行：
- `npm run lint`：确保拆分过程中没有丢失 Hooks 依赖和未定义变量。
- `npm run build`：确保模块导入导出 (import/export) 路径绝对正确。
