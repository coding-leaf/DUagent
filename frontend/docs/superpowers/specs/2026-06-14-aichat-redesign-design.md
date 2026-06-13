# AIChat UI/UX Redesign Specification

## 1. Overview
The current `AIChat.jsx` feels like a "demo" rather than a dedicated learning space. The UI is blocky, lacks a proper empty state, uses hardcoded strings, and the chat messages resemble customer service bubbles rather than an intelligent tutoring system. 

This spec outlines a structural and visual overhaul of the `AIChat` and related components to create an immersive, professional, and competition-ready "Learning Assistant" experience.

## 2. Layout Architecture
Transitioning to a **Three-Column Layout**:
1. **Left Sidebar (Width: ~260px):** History sessions.
2. **Center Column (Flexible, main content):** The core chat experience. Content inside this column is constrained to a max-width (e.g., 760px - 800px) for optimal reading.
3. **Right Sidebar (Width: ~300px):** Dedicated space for "Course Context" and "Resource Recommendations". This ensures resources are prominently displayed for demos, rather than buried under chat messages.

## 3. Component Details

### 3.1 Top Bar / Header
- **Remove:** The large redundant card ("DS 智能答疑专家 / 运行中 / 已就绪").
- **Add:** A lightweight top bar within the center column displaying the current session title or course context. 

### 3.2 Empty State (Welcome Area)
- Display a clean welcome message (e.g., "有什么我可以帮你的吗？").
- **Suggestion Cards:** Display 4 specific, actionable scene cards:
  1. 📖 **解释知识点** (示例: 帮我解释 C 语言指针和数组的关系)
  2. 💻 **分析代码** (示例: 帮我分析这段代码为什么会段错误)
  3. 📚 **推荐资源** (示例: 给我推荐适合复习指针的学习资料)
  4. 🎯 **规划复习** (示例: 我想一周内补齐动态内存分配)
- Clicking a card populates the input box.

### 3.3 ChatMessage (`ChatMessage.jsx`)
- **Visual Style:** "Document-style" reading experience. Remove the white bubble background for AI messages.
- **Typography:** Increase line-height (1.6 - 1.7), use readable text colors (e.g., `text-slate-700`).
- **Avatar:** Kept on the left, but overall flow resembles a well-formatted article.
- **Knowledge Points & Suggestions:** Rendered as clean tags (e.g., `# 指针与数组`) below the message.

### 3.4 Tool Call (`ToolCallCard.jsx`)
- **Visual Style:** Move away from the bulky "dev panel" look.
- Use an elegant, inline loading indicator (e.g., spinning circle or subtle pulse) with student-friendly text (e.g., "正在检索知识库...").

### 3.5 Input Composer
- **Positioning:** Remove the global `fixed bottom-4 left-4 lg:left-[280px] right-4 max-w-[1280px]` positioning.
- **New Layout:** Anchor it to the bottom of the center chat column with sticky or absolute positioning relative to the column. It should naturally align with the chat content width.
- **Style:** Clean pill/card shape, seamless integration with the background.

## 4. Text & Hardcoding Cleanups
- Remove hardcoded phrases like "数据结构掌控者", "DS 智能答疑专家", "随时为您解析复杂结构".
- Ensure these texts pull from dynamic props (e.g., `CourseContext` or Agent configuration).

## 5. Performance / Bundle Notes
- Re-evaluate `react-syntax-highlighter` usage. If code blocks are only small snippets, consider a lighter highlighter or loading it dynamically to reduce bundle size, though this can be handled as a technical optimization task later.
