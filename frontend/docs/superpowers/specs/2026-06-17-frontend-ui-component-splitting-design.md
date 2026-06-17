# Frontend Phase 2: UI Component Splitting Design

## 1. 现状与动机 (Motivation)
在完成了“逻辑与数据抽离（Hook化）”之后，核心页面（如 `StudentProfile.jsx`、`TeacherConsole.jsx`）的内部代码依然长达数百行。它们违背了职责单一原则，所有的 JSX 堆砌在一个组件树内，导致：
- **可读性极差**：寻找特定的 UI 元素（如雷达图）需要在庞大的文件中滚动查找。
- **重渲染性能差**：页面的任何微小状态变动都可能触发整棵庞大 VDOM 树的 Diff。
- **复用率零**：很多原本可以在多处使用的模块（如带统一样式的卡片、表格）被锁死在特定页面中。

## 2. 软件工程与架构选型 (Architecture & Patterns)

本次重构严格遵循以下计算机科学与软件工程理念：

1. **容器与展示型组件模式 (Container / Presentational Pattern)**
   - **Container（容器）**：即现有的 Page（如 `StudentProfile`），它充当大脑。它调用 Hook 获取数据、处理业务流（如提交表单），但不包含具体的复杂 DOM 结构。
   - **Presentational（展示型）**：即将剥离出的新组件。它们充当肌肉，是纯粹的（Pure），没有副作用。它们通过 `props` 接收数据并渲染 UI。这种分离极大提升了组件的**可测试性**。
2. **原子设计方法论 (Atomic Design Methodology)**
   - 我们将对 UI 进行升维组合。提取底层的 `Molecules`（分子组件，如通用的 `StatCard`），并将其组合成 `Organisms`（有机体组件，如 `KnowledgeRadarCard`）。
3. **单一职责原则 (Single Responsibility Principle - SRP)**
   - 一个模块应该只有一个发生变化的原因。拆分后，`StudentListTable.jsx` 只会在“表格样式/列需求变更”时被修改，而不会因为“班级选择器逻辑”被牵连。
4. **关注点分离 (Separation of Concerns - SoC)**
   - 将“界面长什么样”和“数据怎么来”从物理文件层面上进行彻底阻断。

## 3. 重构目标与拆解映射 (Refactoring Targets)

### 3.1 `StudentProfile.jsx` 肢解计划
页面作为 Container 注入 `useStudentProfile`，内部的 JSX 切割并移动至 `src/components/profile/`：
- `ProfileHeader.jsx`：顶部学生基本信息、头像、最后同步时间及刷新按钮区。
- `LearningGoalCard.jsx`：学习方向切换区域。
- `GuidanceLevelCard.jsx`：干预程度（轻微/中度/深度）选择与设置面板。
- `ModalityPreferenceCard.jsx`：学习风格（视觉/听觉/动觉）雷达图或柱状图呈现。
- `KnowledgeCoordinateCard.jsx`：知识坐标轴和能力盲区展示。

### 3.2 `TeacherConsole.jsx` 肢解计划
页面作为 Container 注入 `useTeacherConsoleData`，内部 JSX 切割并移动至 `src/components/teacher/`：
- `ClassSelector.jsx`：班级切换 Tabs 或下拉框及复制邀请码区。
- `ClassInsightsPanel.jsx`：班级整体学习状态的大盘（活跃人数、平均分等 StatCard 组合）。
- `StudentMonitoringTable.jsx`：学生名单、分数、在线状态的表格渲染。
- `ResourceManagementPanel.jsx`：按章节分组的学习资源手风琴组件。

### 3.3 全局公共组件池 (Common Components)
从上述拆解中提取跨业务域可复用的 UI 到 `src/components/common/`：
- `SectionHeader.jsx`：页面内带左侧装饰线的模块标题栏。
- `StatCard.jsx`：通用的大数字统计指标卡片。
- `EmptyState.jsx`：无数据时的插画与提示文字容器。

## 4. 实施纪律 (Constraints)
1. **禁止越权操作**：所有的展示型组件内部**严禁**直接 import API service 或发送网络请求，必须通过父级传入的数据或回调函数 (`onUpdate`, `onClick`) 来与外界通信。
2. **避免深层嵌套 (Prop Drilling)**：本次拆解仅做 1~2 层深度的扁平化拆分，以维持状态传递的清晰性。
3. **确保测试通过**：每次拆解一个组件后，必须通过 `npm run build` 确保前端构建不抛出引用异常。
