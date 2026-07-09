# UI Layout Split & Readability Optimization Design Spec

## 1. Goal Description
This document specifies the design for splitting the **Learning Effects Summary** (学习效果总结) card into two distinct components and optimizing their text readability (font sizes, layout, and spacing) in the **Learning Effects** (学习效果展示) page.

Currently, the learning effects summary is packed inside a single wide card (`col-span-8`) that places student diagnostics and recommendations side-by-side. This results in:
1. **Extremely Small Font Sizes**: Text-heavy columns use `text-xs` (12px), making paragraphs hard to read.
2. **Cramped Visual Space**: The diagnostics grid (Scope, Mastery, Behavior) and suggestions list are squeezed into a narrow space next to each other, creating an unbalanced layout and visually dense clusters.

We will split the suggestions block into a dedicated full-width card and increase the text sizes to `text-sm` (14px) and `text-base` (16px) to make the page feel premium, legible, and visually balanced.

---

## 2. Proposed Changes

### 2.1 [NEW] [EffectsSuggestionsCard.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/effects/EffectsSuggestionsCard.jsx)
Create a new standalone card component dedicated to displaying the "Next Steps Learning Suggestions" (下一步学习建议).
- **Structure**:
  - Main container: Standard frosted card (`bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100`).
  - Title header: Emerald theme, icon `check_circle`, title `下一步学习建议` (text-xl, font-bold).
  - Suggestions Prefix: Display the grade level guidelines text in `text-sm text-slate-500 mb-4`.
  - Grid: Use `grid grid-cols-1 md:grid-cols-3 gap-6` to distribute up to 3 recommendations horizontally on desktop and stack them vertically on mobile.
- **Card Spacing & Typography**:
  - Individual recommendation cards: `bg-white border border-slate-100 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow flex gap-3 items-start`.
  - Number Badge: A circular emerald badge `w-6 h-6 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold flex-shrink-0 flex items-center justify-center`.
  - Suggestion Title: `text-base font-bold text-slate-800 mb-1.5`.
  - Suggestion Description: `text-sm text-slate-500 leading-relaxed`.

### 2.2 [MODIFY] [EffectsSummaryCard.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/effects/EffectsSummaryCard.jsx)
Refactor the existing summary card to display exclusively diagnostics: "Scope" (学习范围), "Current Mastery" (当前掌握), and "Learning Behavior" (学习行为).
- **Structure**:
  - Remove the right-hand column container and the conditional rendering of `parsed.suggestions`.
  - Remove the horizontal split `flex flex-col lg:flex-row gap-6` and make the grid occupy the full width.
  - The nested sub-grid remains: `grid grid-cols-1 sm:grid-cols-2 gap-4 content-start`.
- **Typography & Padding**:
  - Diagnostics blocks padding: Increase from `p-4` to `p-5`.
  - Paragraph text size: Increase from `text-xs` to `text-sm` (14px).
  - Paragraph line height: `leading-relaxed` with text color set to `text-slate-700` for higher contrast.

### 2.3 [MODIFY] [LearningEffects.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/LearningEffects.jsx)
Integrate the newly created `EffectsSuggestionsCard` and modify the overall grid layout structure.
- **Layout Restructure**:
  - **First Row**: Keep the `grid grid-cols-12 gap-6`.
    - Left column (`col-span-12 lg:col-span-8`): Render `EffectsSummaryCard` (which is now shorter in height).
    - Right column (`col-span-12 lg:col-span-4`): Render `MasteryDistributionCard` (which aligns nicely with the shorter diagnostic card).
  - **Second Row** (New): If `effectsData?.summary_text` is present, render `EffectsSuggestionsCard` inside a full-width container (`w-full mt-6` or as part of the vertical `space-y-6` stack).
  - **Third Row**: Render `KnowledgeProgressTable`.

---

## 3. Verification Plan

### 3.1 Automated Tests
- Create a new unit test for the suggestions card:
  - [NEW] [EffectsSuggestionsCard.test.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/effects/EffectsSuggestionsCard.test.jsx)
    - Verifies that the suggestions list parses properly and renders recommendations inside a 3-column layout.
    - Verifies empty states handle fallback gracefully.
- Run the full unit test suite:
  - `cd frontend && npm run test:unit`
- Verify linting and build compiles cleanly:
  - `cd frontend && npm run lint && npm run build`

### 3.2 Manual Verification
- Navigate to the **Learning Effects** page (`/learning-effects` or the summary panel) and verify:
  - First-row diagnostics text is larger (`text-sm`) and has comfortable spacing.
  - Next Steps recommendations display in a beautiful 3-column layout below the first row.
  - Sizing is responsive when viewport width changes.
