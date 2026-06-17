# Frontend Refactoring Spec: LearningEffects Page

**日期：** 2026-06-18  
**领域：** 前端 UI 与数据流重构 (LearningEffects.jsx)  
**状态：** 设计审查中  

---

## 1. 架构选型与模式设计 (Architecture & Design Patterns Selection)

为了对齐 Phase 2 顶层设计架构规范（`docs/superpowers/specs/2026-06-17-phase2-architecture-refactoring-master-plan.md`），我们针对 `LearningEffects.jsx` 页面的重构做出以下架构与设计模式选型：

### 1.1 展示与容器分离模式 (Container/Presentational Component Pattern)
* **选用原因**：目前 `LearningEffects.jsx` 混杂了大量的展现布局与复杂的业务细节（如时间格式化、表格操作跳转、掌握度状态条分配等），极难维护与测试。拆分为无状态的展示组件（Presentational Components）与一个顶层的状态组装容器（Container），能够提升可读性和组件复用性。
* **分拆目标**：
  * **主页面容器** `LearningEffects.jsx`：仅负责路由、主布局、以及调用 Custom Hook 获取数据。
  * **数据指标卡** `EffectsOverviewCards.jsx`：展示节点总数、最近评估时间等 5 个指标。
  * **掌握度看板** `MasteryDistributionCard.jsx`：展示 A/B/C、薄弱、待练习等不同进度的分布条。
  * **节点列表表格** `KnowledgeProgressTable.jsx`：以列表展示每个知识图谱节点的掌握分、耗时、证据来源和操作。

### 1.2 自定义 Hook 模式 (Custom Hook Pattern) + SWR 动态轮询 (Dynamic Polling)
* **选用原因**：旧代码中混杂了手写的 `window.setInterval` 去轮询重新评估的异步任务，且通过手动触发 `loadEffects` 存在竞态风险，且缺少 cleanup 易导致内存泄漏。
* **具体做法**：
  * 提取 `useLearningEffects` 自定义 Hook。
  * 用 `useSWR` 代替手动 `useEffect` 获取学习效果数据，实现网络状态重连刷新。
  * 通过 SWR 的 `refreshInterval` 动态判定功能，当检测到 active 任务处于 `processing` 状态时启用 `1500ms` 的短轮询；一旦任务进入 `completed` / `failed` 终端状态，自动停止轮询并触发数据重新拉取（`mutate`）。

### 1.3 工具函数剥离与纯净化
* **选用原因**：去除组件内部内联的 `formatDuration`, `formatDate`, `normalizeRows` 等纯展示函数，将其统一写入子组件的顶层或工具库中，使 UI 组件回归成功态渲染的纯粹视图。

---

## 2. 详细重构规划 (Detailed Refactoring Plan)

### 2.1 新建自定义 Hook: `src/hooks/useLearningEffects.js`
封装所有 SWR 数据拉取、评估任务轮询与数据同步动作：

* **状态接口：**
  * `effectsData` (effectsRes?.data): 当前评估效果数据
  * `effectsLoading`: 数据加载状态
  * `effectsError`: 数据拉取错误
  * `refreshTask`: 当前轮询的任务状态
  * `isPolling`: 是否处于评估中
  * `handleRefresh()`: 触发重新评估的异步函数

### 2.2 新建展示组件

#### 1) `src/components/effects/EffectsOverviewCards.jsx`
* **职责**：渲染五维评估概览卡片。
* **参数 (Props)**：
  * `overview`: `{ total, practiced, pending, defaultPass }`
  * `generatedAt`: `string` (最近评估时间)

#### 2) `src/components/effects/MasteryDistributionCard.jsx`
* **职责**：渲染掌握度分布进度条看板。
* **参数 (Props)**：
  * `masteryDistribution`: `Array<{ key, label, count, color }>`
  * `totalNodes`: `number`

#### 3) `src/components/effects/KnowledgeProgressTable.jsx`
* **职责**：渲染图谱节点进度明细表格。
* **参数 (Props)**：
  * `nodeRows`: `Array`
  * `activeCourseId`: `string`

### 2.3 瘦身主容器: `src/pages/LearningEffects.jsx`
* 清理所有手动 `setInterval`、`setTimeout` 逻辑。
* 替换为调用 `useLearningEffects(activeCourseId)`。
* 将页面结构缩减至 Layout 组装，提升代码的可读性，文件体积分量预计缩减 60%+。

---

## 3. 测试覆盖与验证策略 (Testing & Verification Strategy)

为了保障重构的绝对稳定性（No Regression），我们将采取以下验证步骤：

### 3.1 单元测试：`src/hooks/__tests__/useLearningEffects.test.js`
使用 Vitest 框架对新剥离 of Hook 进行全方位测试：
1. **测试用例 1**：当 `activeCourseId` 缺失时，不发起 API 请求。
2. **测试用例 2**：成功获取学习效果数据时，正确返回 `effectsData` 并结束 `effectsLoading`。
3. **测试用例 3**：点击“重新评估”时，能正确触发 `refreshEvaluation` 并在 `task_id` 有效时启动 SWR 任务轮询。
4. **测试用例 4**：当评估任务状态由 `processing` 变更为 `completed` 时，能正确触发底层 `mutateEffects` 重新拉取效果。

### 3.2 语法与构建验证
每次重构修改完毕后，必须运行以下命令通过检查方可 commit：
* `npm run lint` — 校验代码风格与 React hooks 依赖完整性。
* `npm run build` — 校验打包，确保 import/export 依赖路径绝对正确。
* `npm run test:unit` — 运行全量单元测试（包含新增的 Hook 测试），必须全绿。

---

## 4. 落地步骤建议 (Implementation Steps)

1. 创建 `src/hooks/useLearningEffects.js`。
2. 创建单元测试 `src/hooks/__tests__/useLearningEffects.test.js`，运行 `npm run test:unit` 驱动测试。
3. 创建展示组件 `src/components/effects/EffectsOverviewCards.jsx`、`MasteryDistributionCard.jsx`、`KnowledgeProgressTable.jsx`。
4. 替换 `src/pages/LearningEffects.jsx`，移除非必要的 state 与 effect。
5. 运行 `npm run lint` 与 `npm run build` 最终验收。
