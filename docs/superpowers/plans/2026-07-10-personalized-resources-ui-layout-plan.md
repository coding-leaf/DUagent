# Unified UI Layout, Contrast & UX Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize UI layouts, correct color contrast ratios, map missing icon variables, implement pointer-events filters, and implement efficient backend count and limit queries for the Personalized Resources and Learning Path pages.

**Architecture:** We will register missing mappings in Icon.jsx (including the new explore compass mapping), convert PersonalizedResources.jsx list styles to 2-column responsive grids, update royal blue styles in PathVisualizer.jsx/NodeResourcePanel.jsx to cyan brand accents, prune double borders, and optimize NodeResourceService.py queries.

**Tech Stack:** React 19, Tailwind CSS v4, Lucide React, FastAPI, SQLAlchemy, SQLite, Vitest, Pytest.

---

### Task 1: Update Icon Component Mappings

**Files:**
- Modify: `frontend/src/components/Icon.jsx`

- [ ] **Step 1: Map expand_less, expand_more, description, play_circle, and explore in Icon.jsx**

Modify the `materialToLucide` dictionary in `frontend/src/components/Icon.jsx` to map missing icons:
```diff
@@ -19,6 +19,8 @@
     'lock': 'Lock',
     'error': 'AlertCircle',
     'chevron_right': 'ChevronRight',
+    'expand_less': 'ChevronUp',
+    'expand_more': 'ChevronDown',
     'check_circle': 'CheckCircle2',
     'arrow_forward': 'ArrowRight',
     'arrow_back': 'ArrowLeft',
@@ -77,6 +77,7 @@
     'do_not_disturb_off': 'Ban',
     'check': 'Check',
     'chat_bubble': 'MessageCircle',
+    'explore': 'Compass',
     'bookmark': 'Bookmark',
     'block': 'Ban',
     'badge': 'Badge',
@@ -83,6 +84,8 @@
     'attach_file': 'Paperclip',
     'assignment': 'ClipboardList',
     'arrow_upward': 'ArrowUp',
+    'description': 'FileText',
+    'play_circle': 'PlayCircle',
     'analytics': 'BarChart2',
```

- [ ] **Step 2: Verify frontend compilation**
Run: `npm run build` inside `frontend/` directory.
Expected: Build passes with no compilation errors.

- [ ] **Step 3: Commit**
```bash
git add frontend/src/components/Icon.jsx
git commit -m "style(fe): map expand arrows, compass, and file/video icons in Icon.jsx"
```

---

### Task 2: Optimize Cards Layout, Contrast, and UX in PersonalizedResources.jsx

**Files:**
- Modify: `frontend/src/pages/PersonalizedResources.jsx`

- [ ] **Step 1: Refactor QuizGroupCard in PersonalizedResources.jsx**
Make headers use `p-5`, replace low-contrast buttons, map the updated expand chevron, and prevent accidental deletion clicks:
```javascript
// ... (Make container hover style shadow-md hover:border-cyan-300 hover:bg-cyan-50/5)
// ... (Make header p-5, gap-4)
// ... (Make play button bg-cyan-600 hover:bg-cyan-700 text-white shadow-sm)
// ... (Make delete button opacity-0 group-hover/item:opacity-100 pointer-events-none group-hover/item:pointer-events-auto)
```

- [ ] **Step 2: Refactor ResourceCard in PersonalizedResources.jsx**
Standardize card layout to `p-5 gap-4` and add pointer-events classes to the absolute positioned delete button:
```javascript
// ... (Make link container p-5, gap-4)
// ... (Color-code tag badges: wrong answers are bg-red-50 text-red-600; manual is bg-cyan-50 text-cyan-600)
// ... (Make delete button pointer-events-none group-hover:pointer-events-auto)
```

- [ ] **Step 3: Refactor Main Containers to Responsive Grid Layout**
Update active filter tabs to use cyan brand colors, and replace list containers from `space-y-3` to `grid grid-cols-1 md:grid-cols-2 gap-4`.

- [ ] **Step 4: Run unit tests**
Run: `npm run test:unit` inside `frontend/` directory.
Expected: PASS.

- [ ] **Step 5: Verify build compilation**
Run: `npm run build` inside `frontend/` directory.
Expected: Build passes cleanly.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/pages/PersonalizedResources.jsx
git commit -m "style(fe): convert personalized resources to 2-column grid and enhance contrast/UX"
```

---

### Task 3: Backend Exercise Count and Limit Optimizations

**Files:**
- Modify: `backend/app/services/node_resource_service.py`

- [ ] **Step 1: Implement _full_exercise_count in node_resource_service.py**

Add the helper method `_full_exercise_count` to fetch total active quiz question count in the database:
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

- [ ] **Step 2: Update _full_exercise_set limit and get_node_resources response**

Modify `_full_exercise_set` to query with a limit of 10 items instead of 50:
```python
    async def _full_exercise_set(self, course_id: str) -> list[dict]:
        result = await self.db.execute(
            select(QuizQuestion)
            .where(
                QuizQuestion.course_id == course_id,
                QuizQuestion.is_deleted == False,
            )
            .limit(10)
        )
        return [
            {"id": question.id, "type": question.type, "content": question.content}
            for question in result.scalars().all()
        ]
```
Add `"full_exercise_count": await self._full_exercise_count(course_id)` to the dictionary returned by `get_node_resources`.

- [ ] **Step 3: Run backend unit tests**

Run: `pytest tests/test_node_resources.py -v` in `backend` directory.
Expected: PASS.

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/node_resource_service.py
git commit -m "perf(be): implement full_exercise_count query and reduce exercise set query size to 10"
```

---

### Task 4: Polish PathVisualizer and NodeResourcePanel in Frontend

**Files:**
- Modify: `frontend/src/components/learning/PathVisualizer.jsx`
- Modify: `frontend/src/components/learning/NodeResourcePanel.jsx`

- [ ] **Step 1: Replace all royal blue styling with brand cyan styling in PathVisualizer.jsx**

Edit `frontend/src/components/learning/PathVisualizer.jsx`:
- Update selected ring class to: `node.id === selectedNodeId ? 'scale-[1.01] transition-all' : ''` (removing the double outer border ring).
- For `node.status === 'in_progress'`, update the card header and details colors:
  - Play button background: `bg-cyan-600`
  - Inner card border: `node.id === selectedNodeId ? 'border-cyan-500 ring-2 ring-cyan-500 ring-offset-1 shadow-lg' : 'border-slate-200'`
  - Progress bar background: `bg-cyan-600`
  - "进行中" badge: `bg-cyan-600`
  - "继续学习" button styles: `bg-cyan-600 hover:bg-cyan-700 text-white border-transparent hover:scale-[1.01] transition-all`
- For `node.status === 'pending'` (unstarted nodes), update the label text to:
  `尚未学习，点击查看资源`
- Add scrollbar-none to the node timeline wrapper: `className="relative flex items-center py-xl overflow-x-auto scrollbar-none min-h-[300px]"`

- [ ] **Step 2: Refactor NodeResourcePanel.jsx colors and count logic**

Edit `frontend/src/components/learning/NodeResourcePanel.jsx`:
- Update "节点练习" card header icon background to `bg-cyan-50 text-cyan-600`.
- Update the choice type badges in the exercise list to `bg-cyan-100 text-cyan-700`.
- Update the "进入练习" action button inside the exercise panel to use `bg-cyan-600 hover:bg-cyan-700 text-white font-bold transition-colors`.
- Change the total count of the collapsed exercises block:
  `共 {nodeResources.full_exercise_count || nodeResources.full_exercise_set?.length || 0} 题`
- Update the empty exercises state (line 107) to render a placeholder button for visual symmetry:
  ```jsx
  <div className="w-full text-center py-4 border border-dashed border-slate-200 text-slate-400 rounded-lg text-sm font-medium bg-slate-50/50">该节点暂无练习</div>
  ```

- [ ] **Step 3: Run frontend unit tests and production build**

Run:
```bash
cd frontend && npm run test:unit && npm run build
```
Expected: All tests pass, production compilation succeeds.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/learning/PathVisualizer.jsx frontend/src/components/learning/NodeResourcePanel.jsx
git commit -m "style(fe): integrate cyan branding and optimize scrollbars, counts, and locked card guides in PathVisualizer"
```
