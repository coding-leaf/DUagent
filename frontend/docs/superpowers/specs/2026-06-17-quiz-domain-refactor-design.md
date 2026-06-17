# 答题链路 (Quiz & PracticeResult) 重构设计规范

## 1. 架构决策总结

### 1.1 MVVM + 容器/展示分离
- **薄容器化**：`Quiz.jsx` 和 `PracticeResult.jsx` 剥离业务逻辑，退化为纯粹的排版容器，仅负责组装各个提取后的展示子组件。
- **ViewModel 提取**：
  - `useQuizEngine.js`：接管 `Quiz.jsx` 的所有 API 调用（获取题目）、埋点追踪 (`node_practice_start`)、以及答题状态（`answers` 字典与 `currentQuestionIndex` 流转）。
  - `usePracticeResult.js`：接管 `PracticeResult.jsx` 中关于结果拉取、后台刷新（`refreshEvaluation`/`refreshProfile`）的逻辑。明确该 Hook 的核心职责为：**一次性延迟拉取**（5s 后触发），而非无限长轮询。

### 1.2 加载状态UI组件提取
- 将 `PracticeResult.jsx` 中利用 `setInterval` 切换文字与 loading UI 的代码提取为单独的纯 UI 组件 `<ResultLoadingState />`，保持主容器整洁。

### 1.3 题型更新派发表 (Dispatch Table)
- 在 `useQuizEngine.js` 中将原有的 `handleAnswerChange` 的多重 `if-else` 改写为 `answerUpdaters` 派发表。
- **扩展性预留**：内置对 `short_answer`（简答题）、`coding`（编程题）的更新预留支持，方便未来轻松接入非选择类题型。

---

## 2. 组件拆解蓝图

| 领域 | 产物 | 职责说明 |
|------|------|----------|
| **Quiz** | `useQuizEngine.js` | 核心 Hook：题库获取 + 埋点记录 + 答题状态流转 (`answerUpdaters`) |
| **Quiz** | `QuizHeader.jsx` | 纯 UI：顶部进度条与当前答题状态显示 |
| **Quiz** | `QuizSidebar.jsx` | 纯 UI：左侧题目元数据面板（补入） |
| **Quiz** | `QuizFooter.jsx` | 纯 UI：上一题 / 下一题 / 提交 的按钮控制区 |
| **PracticeResult** | `usePracticeResult.js` | 核心 Hook：5s 延迟拉取诊断结果，并判断是否刷新后端学情与画像 |
| **PracticeResult** | `ResultLoadingState.jsx` | 纯 UI：带有文字轮播动画的加载视图 |
| **PracticeResult** | `ResultScoreBoard.jsx` | 纯 UI：得分展示圆环与顶部的整体数据统计 |
| **PracticeResult** | `QuestionReviewList.jsx` | 纯 UI：原代码最冗长的题目解析与回顾列表渲染逻辑 |

---

## 3. 现有库复用与代码精简说明

- **基础组件复用**：系统目前生态采用 `Tailwind CSS`，无 `Radix`/`HeadlessUI` 等外挂组件库。但在重构中，题目渲染必须继续复用现有的 `<QuestionRenderer />` 组件，该组件已内建 Markdown 与 Mermaid 解析支持。
- **派发表实现范例**：
  ```javascript
  const answerUpdaters = {
    single_choice: (prev, nextAnswer, qId) => ({ ...prev, [qId]: nextAnswer }),
    multi_choice: (prev, nextAnswer, qId) => {
      const existing = prev[qId] || [];
      const updated = existing.includes(nextAnswer) 
        ? existing.filter(x => x !== nextAnswer) 
        : [...existing, nextAnswer];
      return { ...prev, [qId]: updated };
    },
    short_answer: (prev, nextAnswer, qId) => ({ ...prev, [qId]: nextAnswer }), // 预留简答题文本更新
    coding: (prev, nextAnswer, qId) => ({ ...prev, [qId]: nextAnswer }),       // 预留代码编辑更新
  };
  ```
