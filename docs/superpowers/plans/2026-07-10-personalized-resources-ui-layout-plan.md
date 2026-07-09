# Personalized Resources Page UI Layout & Typography Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Personalized Resources page layout to a responsive 2-column grid, fix low color contrast accessibility issues, map missing chevron and file icons in Icon.jsx, and apply pointer-events mouse filtering to prevent accidental card deletions.

**Architecture:** We will register missing Material-to-Lucide mappings in Icon.jsx, convert list container elements in PersonalizedResources.jsx to Tailwind grid layouts, standardize internal spacing, apply theme primary-color combinations, and disable delete button clicks when transparent.

**Tech Stack:** React 19, Tailwind CSS v4, Lucide React, Vitest, Playwright.

---

### Task 1: Update Icon Component Mappings

**Files:**
- Modify: `frontend/src/components/Icon.jsx:3-110`

- [ ] **Step 1: Map expand_less, expand_more, description, and play_circle in Icon.jsx**

Modify the `materialToLucide` dictionary in `frontend/src/components/Icon.jsx` to map missing icons:
```javascript
const materialToLucide = {
    // ... (lines 4-20)
    'chevron_right': 'ChevronRight',
    'expand_less': 'ChevronUp',
    'expand_more': 'ChevronDown',
    // ... (lines 22-89)
    'arrow_upward': 'ArrowUp',
    'description': 'FileText',
    'play_circle': 'PlayCircle',
    // ...
```

Here is the exact code block mapping update:
```diff
     'error': 'AlertCircle',
     'chevron_right': 'ChevronRight',
+    'expand_less': 'ChevronUp',
+    'expand_more': 'ChevronDown',
     'check_circle': 'CheckCircle2',
```
and:
```diff
     'auto_stories': 'BookOpen',
     'attach_file': 'Paperclip',
     'assignment': 'ClipboardList',
     'arrow_upward': 'ArrowUp',
+    'description': 'FileText',
+    'play_circle': 'PlayCircle',
     'analytics': 'BarChart2',
```

- [ ] **Step 2: Verify frontend compilation**

Run: `npm run build` inside `frontend/` directory.
Expected: Build passes with no compilation errors related to Icon.jsx or missing imports.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Icon.jsx
git commit -m "style(fe): map expand arrows and file/video icons in Icon.jsx"
```

---

### Task 2: Optimize Cards Layout, Contrast, and UX in PersonalizedResources.jsx

**Files:**
- Modify: `frontend/src/pages/PersonalizedResources.jsx`

- [ ] **Step 1: Refactor QuizGroupCard in PersonalizedResources.jsx**

Modify `QuizGroupCard` (lines 37-159) to use standard margins, correct theme button styles, map the updated expand chevron, and prevent accidental deletion clicks:
```diff
@@ -71,28 +71,28 @@
   return (
-    <div className="bg-white border border-outline-variant rounded-xl overflow-hidden hover:shadow-sm transition-shadow">
+    <div className="bg-white border border-outline-variant rounded-xl overflow-hidden hover:shadow-md hover:border-cyan-300 hover:bg-cyan-50/5 transition-all duration-200">
       {/* Header */}
       <div 
-        className="p-4 flex items-center justify-between gap-4 bg-slate-50 cursor-pointer"
+        className="p-5 flex items-center justify-between gap-4 bg-slate-50 cursor-pointer"
         onClick={() => setIsExpanded(!isExpanded)}
       >
-        <div className="flex items-center gap-3 min-w-0">
+        <div className="flex items-center gap-4 min-w-0">
           <div className="w-10 h-10 rounded-full bg-primary-container/10 flex items-center justify-center text-primary-container flex-shrink-0">
             <Icon name="quiz" className="material-symbols-outlined"/>
           </div>
           <div className="min-w-0">
             <h3 className="text-body-md font-bold text-slate-800">{kp}</h3>
             <p className="text-label-sm text-slate-500 mt-1">共 {count} 道个性化题目</p>
           </div>
         </div>
-        <div className="flex items-center gap-3 flex-shrink-0">
+        <div className="flex items-center gap-4 flex-shrink-0">
           <button
             onClick={handleStartPractice}
-            className="flex items-center gap-1.5 px-4 py-2 bg-primary-container text-white rounded-xl text-label-sm font-bold hover:brightness-110 active:scale-95 transition-all"
+            className="flex items-center gap-1.5 px-4 py-2 bg-cyan-600 text-white rounded-xl text-label-sm font-bold hover:bg-cyan-700 active:scale-95 transition-all cursor-pointer shadow-sm"
           >
             <Icon name="play_arrow" className="material-symbols-outlined text-[16px]"/>
             开始练习 {selectedIds.length > 0 ? `(已选 ${selectedIds.length})` : ''}
           </button>
           <Icon name={isExpanded ? 'expand_less' : 'expand_more'} className="material-symbols-outlined text-slate-400"/>
         </div>
       </div>
```

Modify the delete button in `QuizGroupCard` list item to add pointer-events classes:
```diff
@@ -144,3 +144,3 @@
                   <button 
-                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
+                    className="p-1.5 text-slate-400 opacity-0 group-hover/session:opacity-100 pointer-events-none group-hover/session:pointer-events-auto hover:text-red-500 hover:bg-red-50 rounded transition-all"
                     onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
```

- [ ] **Step 2: Refactor ResourceCard in PersonalizedResources.jsx**

Modify `ResourceCard` (lines 161-234) to use standard padding, standard margins, color-coded rounded-md tag badges, and add pointer-events classes to the delete button:
```diff
@@ -201,31 +201,31 @@
   if (item.resource) {
     const r = item.resource;
+    const sourceLabel = SOURCE_LABEL[item.source_type] || item.source_type;
+    const sourceBg = item.source_type === 'quiz_wrong_answer' ? 'bg-red-50 text-red-600' : 'bg-cyan-50 text-cyan-600';
     return (
       <div className="relative group">
-        <Link to={`/resource/${r.id}`} className="block bg-white border border-outline-variant rounded-xl p-md hover:shadow-sm transition-shadow">
-        <div className="flex items-start gap-md">
-          <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center text-secondary flex-shrink-0">
+        <Link to={`/resource/${r.id}`} className="block bg-white border border-outline-variant rounded-xl p-5 hover:shadow-md hover:border-cyan-300 hover:bg-cyan-50/5 transition-all duration-200">
+        <div className="flex items-start gap-4">
+          <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 flex-shrink-0">
             <Icon name={TYPE_ICON[r.type] || 'article'} className="material-symbols-outlined"/>
           </div>
           <div className="flex-1 min-w-0">
-            <div className="flex items-center gap-sm mb-xs flex-wrap">
-              <span className="text-label-sm text-cyan-600 bg-cyan-50 px-2 py-0.5 rounded-full">{r.knowledge_point}</span>
-              <span className="text-label-sm text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full">{SOURCE_LABEL[item.source_type]}</span>
+            <div className="flex items-center gap-2 mb-2 flex-wrap">
+              <span className="text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md">{r.knowledge_point}</span>
+              <span className={`text-[11px] font-medium px-2 py-0.5 rounded-md ${sourceBg}`}>{sourceLabel}</span>
             </div>
             <h4 className="text-body-md font-medium text-on-surface truncate">{r.title}</h4>
             {r.description && <p className="text-label-sm text-secondary mt-1 line-clamp-1">{r.description}</p>}
           </div>
         </div>
       </Link>
       {onDelete && (
         <button 
-          className="absolute top-3 right-3 p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500 hover:bg-red-50 rounded transition-all"
+          className="absolute top-3 right-3 p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto hover:text-red-500 hover:bg-red-50 rounded transition-all"
           onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(item.id); }}
           title="删除"
         >
           <Icon name="delete" className="material-symbols-outlined text-[20px]"/>
         </button>
       )}
```

- [ ] **Step 3: Refactor Main Containers to Responsive Grid Layout**

Modify the main content area in `PersonalizedResources` (lines 304-422) to update the "+ 生成资源" button style, active filter tabs style, and card lists to double-column grids:
```diff
@@ -315,5 +315,5 @@
             <button
               onClick={() => setShowGenerateModal(true)}
-              className="flex items-center gap-2 px-4 py-2 bg-primary-container text-white rounded-xl font-bold hover:brightness-110 active:scale-95 transition-all shadow-sm"
+              className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-xl font-bold hover:bg-cyan-700 active:scale-95 transition-all shadow-sm cursor-pointer"
             >
               <Icon name="add" className="material-symbols-outlined"/>
@@ -342,5 +342,5 @@
                 className={`px-3 py-1.5 rounded-full text-label-sm font-medium transition-colors ${
                   filterSource === opt.value
-                    ? 'bg-primary-container text-white'
-                    : 'bg-surface-container text-secondary hover:bg-surface-container-high'
+                    ? 'bg-cyan-600 text-white shadow-sm'
+                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                 }`}
```

And update the list wraps from `space-y-3` to `grid grid-cols-1 md:grid-cols-2 gap-4`:
```diff
@@ -377,5 +377,5 @@
               {groupQuestionsByKp(items).length > 0 && (
                 <div>
                   <h3 className="text-label-sm text-secondary uppercase tracking-wider mb-3">个性化练习题</h3>
-                  <div className="space-y-3">
+                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     {groupQuestionsByKp(items).map(({ knowledge_point: kp, items: kpItems }) => (
```
and:
```diff
@@ -396,5 +396,5 @@
               {items.filter(i => i.resource).length > 0 && (
                 <div>
                   <h3 className="text-label-sm text-secondary uppercase tracking-wider mb-3">个性化学习资源</h3>
-                  <div className="space-y-3">
+                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                     {items.filter(i => i.resource).map(item => (
```

- [ ] **Step 4: Run unit tests**

Run: `npm run test:unit` inside `frontend/` directory.
Expected: PASS (all 110 tests pass, including CodeSandboxCard and PluginRegistry).

- [ ] **Step 5: Verify build compilation**

Run: `npm run build` inside `frontend/` directory.
Expected: Build passes with no compilation errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/PersonalizedResources.jsx
git commit -m "style(fe): convert personalized resources to 2-column grid and enhance contrast/UX"
```
