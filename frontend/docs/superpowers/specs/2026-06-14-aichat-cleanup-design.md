# AI Chat Mock Data Cleanup Design

## 1. Objective
Clear all hardcoded mock data and placeholders in the AI Chat interface to comply with the project constraint: "不允许 mock/假数据内容". Ensure the UI accurately reflects the current state of the backend without prematurely adding logic that circumvents the required Agent retrieval verification phase.

## 2. Changes

### 2.1 Course Context Correction
- **File**: `src/pages/AIChat.jsx`
- **Change**: Replace the usage of `course.title` with `course.name` to correctly fetch and display the active course name in the right sidebar context.

### 2.2 Empty State Prompt Generalization
- **File**: `src/components/chat/ChatEmptyState.jsx`
- **Change**: Add a `courseName` prop. Replace the hardcoded C-language examples with generic versions interpolating the `courseName`. For example, change "帮我解释 指针 的工作原理" to "帮我解释 ${courseName || '当前课程'} 中的关键概念".

### 2.3 Right Sidebar Mock Removal
- **File**: `src/pages/AIChat.jsx`
- **Change**: Remove the two static resource cards ("深入理解指针内存模型" and "C语言核心代码片段").
- **Empty State**: Display a clean empty state indicating "暂无推荐资源", along with a supplementary note: "完成检索能力验证后，这里会展示与本轮知识点相关的课程资源。"

### 2.4 Tool Call State
- Ensure we do not simulate or hardcode fake ToolCalls (like "匹配资源") in the frontend since no real backend integration exists for it yet. The existing `message.toolCalls` rendering logic will be preserved but remain empty.
