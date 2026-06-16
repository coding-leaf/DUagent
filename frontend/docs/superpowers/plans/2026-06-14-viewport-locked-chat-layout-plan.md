# AI Chat Viewport-Locked Chat Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the height of the AI Chat page (`AIChat.jsx`) to exactly 100vh, preventing body scrolling and ensuring the sidebars and reset button remain fixed on screen, while dynamically loading and filtering recommended resources inside the right sidebar based on active conversation knowledge points.

**Architecture:** Use CSS height constraints (`h-screen overflow-hidden` and `h-full`) to lock the viewport layout. Fetch real resources from `learningService.getResources` and match them against the active conversation's `knowledge_points` extracted from the React messages history array.

**Tech Stack:** React 19, Tailwind CSS, Playwright, React Router DOM.

---

### Task 1: Lock Outer Container Height & Lock Sidebars Height on Desktop

**Files:**
- Modify: `src/pages/AIChat.jsx`

- [ ] **Step 1: Lock outer page wrapper and sidebars height**

Modify `src/pages/AIChat.jsx` to lock the outer wrapper to `h-screen overflow-hidden` and sidebars to `lg:h-full`/`xl:h-full`.

Replace:
```jsx
  return (
    <div className="font-body-md text-slate-800 bg-slate-50 min-h-screen flex flex-col">
      <Navbar />

      <div className="flex-1 flex overflow-hidden pt-16">
        
        {/* Left Sidebar - History */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-auto
```

With:
```jsx
  return (
    <div className="font-body-md text-slate-800 bg-slate-50 h-screen flex flex-col overflow-hidden">
      <Navbar />

      <div className="flex-1 flex overflow-hidden pt-16">
        
        {/* Left Sidebar - History */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-full
```

And replace the right sidebar aside class:
```jsx
        {/* Right Sidebar - Resources (Competition Ready) */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-auto
```

With:
```jsx
        {/* Right Sidebar - Resources (Competition Ready) */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-full
```

- [ ] **Step 2: Run ESLint to verify syntax**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add src/pages/AIChat.jsx
git commit -m "style: lock page height to viewport and set sidebars to full height"
```

---

### Task 2: Implement Dynamic Recommended Resources Sidebar

**Files:**
- Modify: `src/pages/AIChat.jsx`

- [ ] **Step 1: Add Link and learningService imports**

Add the imports at the top of `src/pages/AIChat.jsx`.

Replace:
```javascript
import { useState, useEffect, useRef } from 'react';
import { chatService } from '../api/services/chat';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import ChatMessage from '../components/chat/ChatMessage';
import ChatEmptyState from '../components/chat/ChatEmptyState';
```

With:
```javascript
import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { chatService } from '../api/services/chat';
import { learningService } from '../api/services/learning';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import ChatMessage from '../components/chat/ChatMessage';
import ChatEmptyState from '../components/chat/ChatEmptyState';
```

- [ ] **Step 2: Declare resources state and load resources dynamically**

Declare the `resources` state variable and fetch course resources when `activeCourseId` changes.

Replace:
```javascript
  // Collapse & Drawer States
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
  
  const messagesEndRef = useRef(null);
```

With:
```javascript
  // Collapse & Drawer States
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
  
  // Real Resources State
  const [resources, setResources] = useState([]);
  
  const messagesEndRef = useRef(null);
```

And insert the resource loading hook below active session messages hook:
```javascript
  // Fetch messages when active session changes
  useEffect(() => {
    if (activeSession) {
      chatService.getHistory(activeSession).then(res => {
        if (res.code === 200 && res.data) {
          setMessages(normalizeMessages(res.data.messages));
          setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
        }
      }).catch(console.error);
    } else {
      setTimeout(() => setMessages([]), 0);
    }
  }, [activeSession]);

  // Fetch resources when active course changes
  useEffect(() => {
    if (activeCourseId) {
      learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 100 })
        .then(res => {
          if (res.code === 200 && res.data) {
            const list = res.data.resources || res.data;
            setResources(Array.isArray(list) ? list : []);
          }
        })
        .catch(console.error);
    } else {
      setResources([]);
    }
  }, [activeCourseId]);
```

- [ ] **Step 3: Extract active knowledge points and filter recommended resources**

Add knowledge points helper and filter resources before return in `AIChat`.

Replace:
```javascript
  const handleSendMessage = (overrideText = '') => {
```

With:
```javascript
  const getActiveKnowledgePoints = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.knowledge_points && msg.knowledge_points.length > 0) {
        return msg.knowledge_points;
      }
    }
    return [];
  };

  const activeKPs = getActiveKnowledgePoints();
  const recommendedResources = resources.filter(res => {
    if (activeKPs.length === 0) return true; // Show all if no knowledge points mentioned yet
    return activeKPs.some(kp => 
      res.knowledge_point?.toLowerCase().includes(kp.toLowerCase()) ||
      res.title?.toLowerCase().includes(kp.toLowerCase())
    );
  });

  const handleSendMessage = (overrideText = '') => {
```

- [ ] **Step 4: Render dynamic recommended resources in right sidebar**

Replace the static mock list rendering inside the right sidebar contents.

Replace:
```jsx
            <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
              <div className="flex justify-between items-center mb-4">
                <span className="text-[12px] font-bold text-slate-400">相关资源推荐</span>
                <span className="text-[12px] text-cyan-600 cursor-pointer hover:underline">全部</span>
              </div>
              
              {/* Empty State */}
              <div className="border border-slate-200 border-dashed rounded-xl p-4 bg-slate-50 flex flex-col items-center justify-center text-center mt-6">
                <div className="w-12 h-12 bg-slate-100 rounded-full mb-3 flex items-center justify-center text-slate-400">
                  <span className="material-symbols-outlined text-2xl">inventory_2</span>
                </div>
                <div className="text-[14px] font-semibold text-slate-700 mb-1">暂无推荐资源</div>
                <div className="text-[12px] text-slate-500 leading-relaxed px-2 mt-2">
                  完成检索能力验证后，这里会展示与本轮知识点相关的课程资源。
                </div>
              </div>
            </div>
```

With:
```jsx
            <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
              <div className="flex justify-between items-center mb-4">
                <span className="text-[12px] font-bold text-slate-400">相关资源推荐</span>
                {activeKPs.length > 0 && (
                  <span className="text-[12px] text-cyan-600 cursor-default select-none">
                    推荐中 ({recommendedResources.length})
                  </span>
                )}
              </div>
              
              <div className="space-y-3">
                {recommendedResources.map(res => (
                  <Link
                    key={res.id}
                    to={`/resource/${res.id}`}
                    className="block p-3.5 bg-slate-50 hover:bg-cyan-50/30 border border-slate-200/60 rounded-xl transition-all group cursor-pointer"
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="material-symbols-outlined text-[15px] text-cyan-600 select-none">
                        {res.type === 'mindmap' ? 'hub' : res.type === 'code' ? 'code' : 'description'}
                      </span>
                      <span className="text-[10px] font-bold text-slate-400 bg-white px-2 py-0.5 rounded border border-slate-100 uppercase select-none">
                        {res.type === 'mindmap' ? '导图' : res.type === 'code' ? '代码' : '文档'}
                      </span>
                    </div>
                    <h4 className="text-[13px] font-bold text-slate-700 group-hover:text-cyan-700 transition-colors line-clamp-1 font-body-sm">
                      {res.title}
                    </h4>
                    <p className="text-[11px] text-slate-500 line-clamp-2 mt-1 leading-relaxed">
                      {res.description || '暂无推荐描述信息'}
                    </p>
                  </Link>
                ))}

                {recommendedResources.length === 0 && (
                  <div className="border border-slate-200 border-dashed rounded-xl p-4 bg-slate-50 flex flex-col items-center justify-center text-center mt-6">
                    <div className="w-12 h-12 bg-slate-100 rounded-full mb-3 flex items-center justify-center text-slate-400">
                      <span className="material-symbols-outlined text-2xl">inventory_2</span>
                    </div>
                    <div className="text-[14px] font-semibold text-slate-700 mb-1">暂无推荐资源</div>
                    <div className="text-[12px] text-slate-500 leading-relaxed px-2 mt-2">
                      当前会话中提到的知识点暂无关联的课程资源。
                    </div>
                  </div>
                )}
              </div>
            </div>
```

- [ ] **Step 5: Run final validation and test suite**

Run: `npm run lint`
Expected: PASS

Run: `npm run build`
Expected: PASS

Run E2E regression check: `npx playwright test e2e/specs.spec.js -g "AI Chat renders historical messages"`
Expected: PASS

- [ ] **Step 6: Commit changes**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: implement dynamic recommended resources based on active knowledge points"
```
