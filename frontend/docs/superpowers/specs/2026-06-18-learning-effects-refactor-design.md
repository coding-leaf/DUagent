# Frontend Refactoring Spec: LearningEffects Page

**日期：** 2026-06-18  
**领域：** 前端 UI 与数据流重构 (LearningEffects.jsx)  
**状态：** 设计审查中  

---

## 1. 架构选型与模式设计 (Architecture & Design Patterns Selection)

为了对齐 Phase 2 顶层设计架构规范（`docs/superpowers/specs/2026-06-17-phase2-architecture-refactoring-master-plan.md`），我们针对 `LearningEffects.jsx` 页面的重构做出以下架构与设计模式选型：

### 1.1 展示与容器分离模式 (Container/Presentational Component Pattern)
* **选用原因**：将展现布局、格式化工具函数与复杂的业务细节从页面主文件中抽离，提升测试覆盖率与组件复用性。
* **分拆目标**：
  * **主页面容器** `LearningEffects.jsx`：仅负责页面级的路由、主 Layout 结构装配、API 错误及任务状态横幅展示。
  * **数据指标卡** `EffectsOverviewCards.jsx`：展示节点总数、最近评估时间等 5 个指标。
  * **评估总结卡** `EffectsSummaryCard.jsx`：展示 AI 学习效果总结文本、处理加载态与暂无数据的降级展示。
  * **掌握度看板** `MasteryDistributionCard.jsx`：以列表展示 A/B/C、薄弱、待练习等进度的横向分布条。
  * **进度明细表** `KnowledgeProgressTable.jsx`：以列表表格展示每个节点的详细状态、耗时、证据、分值，并提供练习/查看按钮。

### 1.2 自定义 Hook 模式 (Custom Hook Pattern) 与 双 SWR 协作轮询 (Dual-SWR Collaboration)
* **选用原因**：废除手写的 `window.setInterval` 状态轮询，并彻底杜绝在页面级处理接口状态拉取。采用与 `useStudentProfile.js` 一致的双 SWR 声明式数据获取与任务轮询模式。
* **协作逻辑**：
  1. **主效果数据**：使用 SWR 实例获取学习效果数据，绑定 `['learningEffects', activeCourseId]` Key。
  2. **任务状态轮询**：当且仅当用户点击“重新评估”并创建后台任务后，启动一个独立的 SWR 轮询，Key 为 `['learningEffectsTask', taskId]`，调用 `taskService.getTaskStatus` 接口。
  3. **动态轮询间隔**：通过该 SWR 的 `refreshInterval` 选项判断，若任务仍为非终端状态（`processing`），则保持 `1500ms` 轮询间隔；若变为终端状态（`completed` / `failed` / `partial`），则返回 `0` 停止轮询。
  4. **数据同步**：当轮询检测到任务 `completed` 后，调用主效果数据的 `mutateEffects()` 进行数据刷新。

### 1.3 派生状态下沉 (Derived State in Hook)
* **选用原因**：`overview` (节点统计) 和 `masteryDistribution` (进度占比分布) 是完全依赖于 `effectsData.node_progress` 的派生状态。将派生状态计算、格式化工具函数和状态处理均下沉至 Custom Hook 内，避免容器组件承担多余逻辑。

---

## 2. 详细重构规划 (Detailed Refactoring Plan)

### 2.1 自定义 Hook 状态定义: `src/hooks/useLearningEffects.js`
封装所有数据拉取、派生计算与双 SWR 轮询逻辑：

* **返回的接口字段：**
  * `effectsData` (effectsRes?.data): 原始学习效果数据
  * `effectsLoading`: 效果数据是否处于 SWR 加载中
  * `effectsError`: 效果数据请求错误
  * `refreshTask`: 任务运行状态对象 `{ task_id, status, progress, error_code, error_message }`
  * `isPolling`: 评估任务是否正在运行中 (`status === 'processing'`)
  * `refreshFailed`: 任务是否运行失败或中断 (`terminal` 且非 `completed`)
  * `refreshFailureMessage`: 格式化后的错误异常信息
  * `overview`: 派生的统计数据 `{ total, practiced, pending, defaultPass }`
  * `masteryDistribution`: 派生的掌握度占比分布数据 `{ key, label, count, color }`
  * `handleRefresh()`: 页面触发重新评估的方法

### 2.2 展示组件

#### 1) `src/components/effects/EffectsOverviewCards.jsx`
* **职责**：渲染五维评估概览卡片。
* **参数 (Props)**：
  * `overview`: `{ total, practiced, pending, defaultPass }`
  * `generatedAt`: `string` (最近评估时间)

#### 2) `src/components/effects/EffectsSummaryCard.jsx`
* **职责**：渲染 AI 总结卡片，展示 `effectsData?.summary_text`。
* **参数 (Props)**：
  * `summaryText`: `string`
  * `loading`: `boolean` (对应 effectsLoading 状态)

#### 3) `src/components/effects/MasteryDistributionCard.jsx`
* **职责**：渲染掌握度分布进度条看板。
* **参数 (Props)**：
  * `masteryDistribution`: `Array<{ key, label, count, color }>`
  * `totalNodes`: `number`

#### 4) `src/components/effects/KnowledgeProgressTable.jsx`
* **职责**：渲染图谱节点进度明细表格。内部封装 `formatDuration`, `getMasteryDisplay`, `hasPracticeEvidence` 以及样式映射。
* **参数 (Props)**：
  * `nodeRows`: `Array`
  * `activeCourseId`: `string`

### 2.3 瘦身主容器: `src/pages/LearningEffects.jsx`
* 清理全部内联 calculations、`setInterval` 轮询和辅助展示函数。
* 仅调用 `useLearningEffects(activeCourseId)` 获取结构化数据。
* 组合 `<EffectsOverviewCards>`, `<EffectsSummaryCard>`, `<MasteryDistributionCard>` 和 `<KnowledgeProgressTable>` 构建清晰的 Grid 布局页面。

---

## 3. 测试覆盖与验证策略 (Testing & Verification Strategy)

### 3.1 单元测试：`src/hooks/__tests__/useLearningEffects.test.js`
使用 Vitest 框架对新 Hook 独立覆盖测试：
1. **测试用例 1**：当 `activeCourseId` 缺失时，SWR 不发起请求，且派生字段返回安全初始值。
2. **测试用例 2**：成功获取学习效果数据时，正确输出计算后的 `overview` 与 `masteryDistribution`。
3. **测试用例 3**：在 `refreshTask` 存在且状态为 `processing` 时启动独立的 SWR 轮询（Key 为 `['learningEffectsTask', task_id]`）。
4. **测试用例 4**：当轮询任务完成并返回 `status === 'completed'` 时，触发 `mutateEffects` 重新抓取最新效果数据。
5. **测试用例 5**：当轮询任务返回错误或失败状态时，能够输出派生的 `refreshFailed=true` 和对应的错误文本信息。

### 3.2 语法与构建验证
* `npm run lint` — 校验代码风格。
* `npm run build` — 确保打包成功。
* `npm run test:unit` — 执行单元测试全绿。
