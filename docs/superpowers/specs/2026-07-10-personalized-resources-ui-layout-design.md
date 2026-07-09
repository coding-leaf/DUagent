# Personalized Resources Page UI Layout & Typography Optimization Design Spec

## 1. Goal Description
The "Personalized Resources" (个性化资源) page displays custom generated learning resources and quizzes tailored to the student's study progress. Currently, the page layout and visual hierarchy suffer from several styling and UX issues:
1. **Low Color Contrast**: Buttons (like "+ 生成资源", "开始练习") and active filter tags use `bg-primary-container text-white`. In the current color scheme, the container color is bright cyan (`#00d1ff`), making white text extremely hard to read and violating Web accessibility (WCAG) contrast standards.
2. **Awkward Empty Spaces**: When cards stretch across a single full-width column, the sparse left-aligned text leaves a large, unbalanced empty white region on the right half of every card, creating an "empty" feel.
3. **Placeholder Question Marks (`?`)**: The accordion collapse handle icons (`expand_less`/`expand_more`) and type icons for `document`/`video` resource cards display as circular question marks `(?)`. This is due to missing icon name mappings in the global `Icon.jsx` helper dictionary, triggering fallback rendering.
4. **Delete Button Accidental Triggering**: Card delete buttons are transparent (`opacity-0`) by default and only show on hover. However, they are still clickable when hidden, meaning students clicking the top-right corner of a card (e.g. to open a resource) will accidentally trigger the delete confirmation modal.

This design document outlines the UI overhaul to resolve these defects by transitioning to a flat 2-column grid layout, correcting color contrasts, mapping missing icons, and refining hover interactions.

---

## 2. Proposed Changes

### 2.1 [MODIFY] [Icon.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/Icon.jsx)
We will register the missing icon mappings in the `materialToLucide` dictionary to replace fallback question marks with high-fidelity vector icons:
- `'expand_less': 'ChevronUp'` (collapsible header collapsed state)
- `'expand_more': 'ChevronDown'` (collapsible header expanded state)
- `'description': 'FileText'` (resource document icon)
- `'play_circle': 'PlayCircle'` (resource video icon)

### 2.2 [MODIFY] [PersonalizedResources.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/PersonalizedResources.jsx)

#### 2.2.1 Grid Layout Overhaul
Instead of stack-based lists (`space-y-3`), we will wrap the cards in a responsive grid layout:
- Change the card list containers to:
  `className="grid grid-cols-1 md:grid-cols-2 gap-4"`
- On desktop, cards will display in two side-by-side columns, cutting their width in half and preventing awkward empty space. On mobile, they will automatically fall back to single-column stacking.

#### 2.2.2 Button Contrast & Accessibility
- Replace the high-brightness, low-contrast `bg-primary-container text-white` color scheme on the "+ 生成资源" button, "开始练习" button, and active filter tabs.
- Apply a deep teal brand brand-color combination:
  `bg-cyan-600 hover:bg-cyan-700 text-white transition-all duration-200`
  This aligns the controls with standard AAA color contrast ratios and matches other premium areas of the application.

#### 2.2.3 Card Spacing & Badge Polish
- Replace non-standard spacings (`p-md`, `gap-md`, `gap-sm`, `mb-xs`) with standard Tailwind utilities:
  - Card padding: `p-5` (20px padding) for clean density.
  - Icon-to-content gap: `gap-4` (16px gap).
  - Badge-to-title bottom margin: `mb-2` (8px margin).
- Change badge shapes from capsule pills (`rounded-full`) to standard rounded rectangles (`rounded-md`) to coordinate with the card's `rounded-xl` corners.
- Color code the badges semantically based on the generation source:
  - Manual generated: `bg-cyan-50 text-cyan-600 text-[11px] font-medium px-2 py-0.5 rounded-md`
  - Triggered by wrong answer: `bg-red-50 text-red-600 text-[11px] font-medium px-2 py-0.5 rounded-md`
- Upgrade hover animations on both `QuizGroupCard` and `ResourceCard` to:
  `hover:shadow-md hover:border-cyan-300 hover:bg-cyan-50/10 transition-all duration-200`

#### 2.2.4 Accidental Clicks Prevention
- Add `pointer-events-none group-hover:pointer-events-auto` to the delete buttons in both `QuizGroupCard` and `ResourceCard`.
- This ensures that when the delete button is invisible (`opacity-0`), clicks are ignored, preventing accidental clicks.

---

## 3. Verification Plan

### 3.1 Automated Tests
- Run the full Vitest suite to ensure no React component breaks due to layout structure changes:
  ```bash
  cd frontend && npm run test:unit
  ```
- Validate that the production bundles compile cleanly without syntax errors:
  ```bash
  cd frontend && npm run build
  ```

### 3.2 Manual Verification
- Deploy and open `/personalized-resources` in the browser.
- Verify that:
  - Accordion chevrons render as up/down arrows, and document/video icons render correctly.
  - Active tabs and buttons have dark blue text or darker backgrounds with white text.
  - The cards arrange in two columns on wide viewports, and flow in one column on mobile screens.
  - Clicking on the top-right corner of a card (when mouse is not hovered) does not trigger the deletion confirmation dialog.
