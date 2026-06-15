# Frontend Code Optimization Design Spec

## 1. 背景 (Background)
当前 EDUagent 前端项目的功能已基本实现并稳定运行，但在业务演进过程中，代码逐渐积累了一些技术债：
1. **巨型组件问题**：例如 `StudentProfile.jsx` (近 1000 行)、`AIChat.jsx` (600+ 行)、`LearningPath.jsx` 等。组件承担了过多的 UI 渲染、状态管理、API 交互等职责，违反了单一职责原则，导致可读性和后期维护难度极高。
2. **首屏加载瓶颈**：在 `App.jsx` 中所有路由组件（包括学生端、教师端、管理端）和重度依赖（如 ECharts、Mermaid 等）均被静态 `import`，导致应用首屏下载了大量当前角色并不需要的代码。
3. **渲染性能隐患**：状态全量堆积在顶层页面组件，导致任何局部状态更新（如输入框文字变化）都可能引起整个深层组件树的无效重渲染（Re-render）。

**本次优化目标**：在**不改变现有任何业务逻辑和界面功能**的前提下，对前端代码进行重构与优化，提升代码的健壮性、可维护性和应用的加载/运行性能。

---

## 2. 优化方案设计 (Proposed Architecture & Optimizations)

### 2.1 巨型组件拆分与逻辑解耦 (Component & Logic Decoupling)
将现有的巨型页面拆分为“容器组件 (Container) + 纯展示组件 (Presentational) + 自定义 Hook”的模式。

*   **逻辑抽离 (Custom Hooks)**: 
    *   将 `StudentProfile.jsx` 中的状态和 API 请求抽离为 `useStudentProfile.js`。
    *   将 `AIChat.jsx` 中的轮询、消息收发等逻辑提取为 `useChatManager.js`。
*   **UI 细粒度拆分 (Sub-components)**:
    *   以 `StudentProfile` 为例，将其拆分为 `<ProfileHeader />`、`<RadarStats />`、`<GuidancePanel />` 和 `<GoalForm />` 等子组件，页面顶层仅负责组装子组件。
*   **收益**：缩小单文件体积（目标控制在 300 行以内），大幅提升代码可读性与复用性。

### 2.2 路由懒加载与包体积优化 (Lazy Loading & Bundle Optimization)
基于 React Router 实施代码分割（Code Splitting），减少首屏加载的 JS 体积。

*   **按角色拆分 Chunk**:
    *   在 `App.jsx` 中，对所有页面组件（特别是体积庞大的 `/admin` 和 `/teacher` 相关页面）使用 `React.lazy()` 配合 `<Suspense>` 进行动态导入。
    *   确保未登录用户或普通学生用户在进入系统时，不会下载管理员专用的庞大模块。
*   **重依赖按需加载**:
    *   将如 `MermaidDiagram` 等包含重型解析器的组件改为按需加载，避免拖慢全局解析时间。
*   **收益**：首屏 JS 文件体积预计可缩减 40% 以上，显著提升 LCP (Largest Contentful Paint) 指标。

### 2.3 渲染性能调优 (Rendering Performance)
消除由于状态更新带来的雪崩式无意义重渲染。

*   **隔离高频状态**:
    *   将如 `inputValue` 等高频更新的状态移动到独立的输入框子组件内部，防止其触发父组件（如整个对话列表）的更新。
*   **应用缓存 Hooks (`useMemo` / `useCallback`)**:
    *   对 `courses.find`、`map` 等需要遍历庞大数组的操作使用 `useMemo` 缓存计算结果。
    *   将传递给子组件的事件回调函数（如 `handleSendMessage`, `fetchProfile`）使用 `useCallback` 进行包裹，配合 `React.memo` 避免子组件被无辜重置。
*   **收益**：操作体验更加丝滑，减少浏览器渲染主线程的压力。

---

## 3. 约束与原则 (Constraints)
1. **零业务变更**：严格保证页面功能、API 接口契约、CSS 样式视觉效果与重构前完全一致。
2. **循序渐进**：优先处理体积最大、最核心的痛点文件（如 `StudentProfile.jsx` 和 `App.jsx`）。
3. **回归测试**：每次重构拆分后必须运行现有的 ESLint 和端到端（如果有）测试。
