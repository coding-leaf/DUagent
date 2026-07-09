# Unified UI Layout, Contrast & UX Optimization Design Spec

## 1. Goal Description
This document specifies the design for unified UI layout, accessibility contrast, and interactive UX optimizations across the **Personalized Resources** (个性化资源) page and the **Learning Path Planning** (学习路径规划) page.

Currently, these pages suffer from several styling, accessibility, and backend query efficiency defects:
1. **Low Color Contrast & Harsh Royal Blue**: 
   - Personalized Resources pages use bright cyan (`bg-primary-container text-white`), violating WCAG contrast ratios.
   - Learning Path pages use hardcoded Royal Blue (`blue-600`/`blue-500`/`blue-700`) colors that look glaring and clash with the system's primary teal brand theme.
2. **Awkward Page Empty Spaces**: 
   - Cards stretch across a single column in Personalized Resources, leaving massive empty white space on the right side of the page.
3. **Placeholder Question Marks (`?`)**: 
   - Missing Lucide icon mappings in `Icon.jsx` for `expand_less`/`expand_more` (accordions), `description`/`play_circle` (resource types), and `explore` (unstarted stage status) trigger default fallback rendering of `HelpCircle` (question marks inside circles).
4. **Delete Button Accidental Triggering**: 
   - Delete buttons on resource cards are transparent (`opacity-0`) but still clickable, leading to accidental delete actions.
5. **Locked Nodes Visual Guidance**: 
   - Greyed out "尚未学习" nodes lack call-to-action text guiding students how to unlock or trigger them.
6. **Hardcoded Limits & Mismatched Total Exercise Counts**: 
   - The backend query for the chapter's "全部练习集" (All exercises set) hardcodes `.limit(50)` and returns full records. The frontend shows a hardcoded `共 50 题` count based on this array length, wasting payload bytes (since the frontend only previews 10 items) and displaying incorrect database totals.

We will resolve these issues with a cohesive design system, unified brand colors, mapped icon fonts, grid restructuring, and database query optimizations.

---

## 2. Proposed Changes

### 2.1 [MODIFY] [Icon.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/Icon.jsx)
Add the missing icon mappings in the `materialToLucide` mapping dictionary:
- `'expand_less': 'ChevronUp'` (accordion collapsed handle)
- `'expand_more': 'ChevronDown'` (accordion expanded handle)
- `'description': 'FileText'` (resource document icon)
- `'play_circle': 'PlayCircle'` (resource video icon)
- `'explore': 'Compass'` (unstarted stage status icon)

### 2.2 [MODIFY] [PersonalizedResources.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/PersonalizedResources.jsx)
- **Grid Layout**: Replace `space-y-3` containers with `grid grid-cols-1 md:grid-cols-2 gap-4` to split content into a modern double-column grid on desktop while maintaining vertical stacks on mobile.
- **Color Contrast**: Update active filter tabs, "+ 生成资源", and "开始练习" button class lists from `bg-primary-container text-white` to the primary brand colors:
  `bg-cyan-600 hover:bg-cyan-700 text-white transition-all shadow-sm cursor-pointer`
- **Card Spacing & Badges**: 
  - Standardize paddings to `p-5` and gaps to `gap-4`.
  - Transform badges from `rounded-full` pills to `rounded-md` rectangles.
  - Color-code badges: `bg-red-50 text-red-600` for wrong answer triggers; `bg-cyan-50 text-cyan-600` for manual generation.
- **Accidental Clicks Prevention**: Add `pointer-events-none group-hover:pointer-events-auto` to absolute positioned delete buttons.

### 2.3 [MODIFY] [PathVisualizer.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/learning/PathVisualizer.jsx)
- **Teal Branding**: Replace all occurrences of `blue-600`, `blue-500`, `blue-700` and `ring-blue-500` with the brand cyan color family: `cyan-600`, `cyan-500`, `cyan-700`.
- **Double Borders Cleanup**: Remove the outer column container ring (`ring-2 ring-offset-2`) when a node is selected. Apply selection highlights exclusively to the inner card component using:
  `ring-2 ring-cyan-500 border-transparent shadow-lg scale-[1.01]`
- **Continue Learning Button Style**: Change the "继续学习" button inside the active stage card to a primary action button:
  `bg-cyan-600 hover:bg-cyan-700 text-white border-transparent shadow-sm hover:scale-[1.01]`
- **UX Guidance**: Update the "尚未学习" status label inside unstarted card components to:
  `尚未学习，点击查看资源`
- **Scrollbar Polish**: Add `scrollbar-none` or custom thin scrollbar styles to the horizontal node visualizer container.

### 2.4 [MODIFY] [NodeResourcePanel.jsx](file:///home/yezisama/workspace/workflow/EDUagent/frontend/src/components/learning/NodeResourcePanel.jsx)
- **Teal Branding**: Replace `bg-blue-50 text-blue-600`, `bg-blue-100 text-blue-700`, and `bg-blue-600 text-white hover:bg-blue-700` with:
  - Header badge: `bg-cyan-50 text-cyan-600`
  - Tag badges: `bg-cyan-100 text-cyan-700`
  - Action button: `bg-cyan-600 hover:bg-cyan-700 text-white font-bold transition-colors`
- **Real Question Count**: Change the displayed total count in the collapsed All Exercises header (line 169) to fetch the true database count:
  `共 {nodeResources.full_exercise_count || nodeResources.full_exercise_set?.length || 0} 题`
- **Empty Practice State**: Render a placeholder button styled like a secondary action card at the bottom of the middle column when there are no exercises, keeping height consistent:
  `<div className="w-full text-center py-2 border border-dashed border-slate-200 text-slate-400 rounded-lg text-sm font-medium bg-slate-50/50">该节点暂无练习</div>`

### 2.5 [MODIFY] [node_resource_service.py](file:///home/yezisama/workspace/workflow/EDUagent/backend/app/services/node_resource_service.py)
- **Real-time Count Query**: Add `_full_exercise_count` to return the count of all active questions under the course:
  ```python
  async def _full_exercise_count(self, course_id: str) -> int:
      result = await self.db.execute(
          select(func.count(QuizQuestion.id)).where(
              QuizQuestion.course_id == course_id,
              QuizQuestion.is_deleted == False,
          )
      )
      return result.scalar() or 0
  ```
- **Byte Reduction Limit**: Decrease the fetched array size of `_full_exercise_set` from 50 to 10 questions to speed up request payloads, since the frontend only displays 10 questions:
  `select(QuizQuestion).where(...).limit(10)`
- **Response Schema Update**: Update the returned dictionary of `get_node_resources` to include:
  `"full_exercise_count": await self._full_exercise_count(course_id)`

---

## 3. Verification Plan

### 3.1 Automated Tests
- Run Vitest suite to verify react rendering does not regress:
  ```bash
  cd frontend && npm run test:unit
  ```
- Run python tests to confirm node_resource_service returns valid counts:
  ```bash
  cd backend && python3 -m pytest tests/test_node_resources.py -v
  ```
- Verify frontend production compiler compiles cleanly:
  ```bash
  cd frontend && npm run build
  ```

### 3.2 Manual Verification
- Navigate to `/learning-path` and confirm:
  - Active nodes use teal/cyan badges instead of harsh royal blue.
  - Hovering and selecting a node scales the card beautifully without double borders.
  - "尚未学习" cards display a Compass icon rather than `(?)`.
  - Selecting "外部变量" updates the bottom panel to show its resources.
  - "全部练习集" total count shows the correct value and expands/collapses properly.
