# AI Chat UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the AI Chat and Agent Workspace into a Modern Canvas & Floating Chat layout to maximize screen efficiency and provide a premium, immersive feel.

**Architecture:** We will convert `AgentWorkspace` into a full-width canvas with a top tab bar to switch between generated artifacts. The `ChatArea` will be transformed into a floating, slightly transparent sidebar overlaid on the right side of the canvas. The `ChatMessage` and input areas will be modernized with pill shapes and soft gradients.

**Tech Stack:** React, Tailwind CSS

---

### Task 1: Update ChatContext to support active artifact tab

**Files:**
- Modify: `frontend/src/context/ChatContext.jsx` (assuming it exists, we will update it to track active tab)

- [ ] **Step 1: Check if ChatContext supports activeArtifactId**
Since we don't know the exact file path for `ChatContext`, we will first inspect it.
Run: `cat frontend/src/context/ChatContext.jsx`

- [ ] **Step 2: Add activeArtifactId state to context**
```javascript
// Add state in ChatProvider
const [activeArtifactId, setActiveArtifactId] = useState(null);

// When adding new artifact, set it as active
// (Find the function that adds to workspaceArtifacts and append setActiveArtifactId)

// Expose in context value
// activeArtifactId, setActiveArtifactId
```

- [ ] **Step 3: Run lint**
Run: `cd frontend && npm run lint`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add frontend/src/context/ChatContext.jsx
git commit -m "feat: add activeArtifactId to ChatContext for tab management"
```

---

### Task 2: Create WorkspaceTabs component and refactor AgentWorkspace

**Files:**
- Create: `frontend/src/components/workspace/WorkspaceTabs.jsx`
- Modify: `frontend/src/components/workspace/AgentWorkspace.jsx`

- [ ] **Step 1: Create WorkspaceTabs**
```javascript
// frontend/src/components/workspace/WorkspaceTabs.jsx
import React from 'react';
import Icon from '../Icon';

export default function WorkspaceTabs({ artifacts, activeId, onSelect }) {
  if (!artifacts || artifacts.length === 0) return null;
  return (
    <div className="flex gap-2 p-2 border-b border-slate-200 overflow-x-auto custom-scrollbar flex-shrink-0">
      {artifacts.map(art => (
        <button
          key={art.id}
          onClick={() => onSelect(art.id)}
          className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
            activeId === art.id 
              ? 'bg-white text-cyan-600 border-t-2 border-cyan-500 shadow-sm' 
              : 'bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-700'
          }`}
        >
          <Icon name="insert_drive_file" className="text-[16px] inline-block mr-1 align-text-bottom" />
          {art.title || art.type}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Modify AgentWorkspace Layout**
```javascript
// In frontend/src/components/workspace/AgentWorkspace.jsx
// Import WorkspaceTabs and activeArtifactId from context
import { useState, useEffect } from 'react';
import { useChat } from '../../context/ChatContext';
import { PluginRegistry } from './PluginRegistry';
import Icon from '../Icon';
import WorkspaceTabs from './WorkspaceTabs';

export default function AgentWorkspace() {
  const { workspaceArtifacts, activeArtifactId, setActiveArtifactId } = useChat();
  
  // Local fallback if context doesn't provide setActiveArtifactId easily
  const [localActiveId, setLocalActiveId] = useState(null);
  const currentActiveId = activeArtifactId || localActiveId;

  useEffect(() => {
    if (workspaceArtifacts.length > 0 && !currentActiveId) {
      setLocalActiveId(workspaceArtifacts[workspaceArtifacts.length - 1].id);
      if (setActiveArtifactId) setActiveArtifactId(workspaceArtifacts[workspaceArtifacts.length - 1].id);
    }
  }, [workspaceArtifacts, currentActiveId, setActiveArtifactId]);

  const activeArtifact = workspaceArtifacts.find(a => a.id === currentActiveId) || workspaceArtifacts[workspaceArtifacts.length - 1];

  return (
    <div className="flex-1 flex flex-col bg-slate-50/50 relative overflow-hidden h-full">
      <div className="flex items-center gap-2 p-4 flex-shrink-0">
        <Icon name="design_services" className="material-symbols-outlined text-slate-600 text-[20px]" />
        <h2 className="text-base font-semibold text-slate-800">Agent 画布</h2>
      </div>

      {workspaceArtifacts.length > 1 && (
        <WorkspaceTabs 
          artifacts={workspaceArtifacts} 
          activeId={currentActiveId} 
          onSelect={(id) => {
            setLocalActiveId(id);
            if (setActiveArtifactId) setActiveArtifactId(id);
          }} 
        />
      )}

      <div className="flex-1 overflow-y-auto custom-scrollbar p-6 bg-white/50 backdrop-blur-sm m-4 mt-0 rounded-2xl border border-slate-200 shadow-sm">
        {workspaceArtifacts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
            <Icon name="dashboard_customize" className="material-symbols-outlined text-[48px] mb-3 text-slate-300" />
            <p className="text-sm">暂无生成产物，请在右侧与 AI 互动生成学习路径、卡片或图表</p>
          </div>
        ) : activeArtifact ? (
          (() => {
            const Component = PluginRegistry[activeArtifact.type];
            if (!Component) {
              return (
                <div className="p-4 bg-red-50 text-red-800 border border-red-200 rounded-xl text-sm">
                  未知插件类型: {activeArtifact.type}
                </div>
              );
            }
            return (
              <div className="transition-all duration-300 animate-fadeIn h-full">
                <Component {...activeArtifact.props} />
              </div>
            );
          })()
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run tests & verify**
Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/workspace/
git commit -m "feat(workspace): refactor AgentWorkspace into a tabbed canvas"
```

---

### Task 3: Redesign AIChat Layout & ChatArea Floating Panel

**Files:**
- Modify: `frontend/src/pages/AIChat.jsx`
- Modify: `frontend/src/components/chat/ChatArea.jsx`
- Modify: `frontend/src/components/chat/ChatArea.test.jsx` (if tests break due to styling changes)

- [ ] **Step 1: Update AIChat.jsx container**
In `frontend/src/pages/AIChat.jsx`, ensure the container holding Workspace and ChatArea is relative, and ChatArea overlaps.
```javascript
// frontend/src/pages/AIChat.jsx
// Change the main flex container
<div className="flex-1 flex overflow-hidden pt-16 relative">
  <SidebarHistory ... />
  <AgentWorkspace />
  
  {/* Wrap ChatArea to make it a floating overlay on the right */}
  <div className="absolute top-0 right-0 h-full p-4 pointer-events-none flex justify-end w-full lg:w-[480px] 2xl:w-[540px] z-10">
    <div className="pointer-events-auto w-full h-full">
      <ChatArea 
        key={activeSession || 'empty'}
        activeCourseName={activeCourseName}
        onOpenLeftDrawer={handleOpenLeftDrawer}
      />
    </div>
  </div>
</div>
```

- [ ] **Step 2: Update ChatArea.jsx styling**
In `frontend/src/components/chat/ChatArea.jsx`:
Change root `<main>` classes:
```javascript
<main className="w-full h-full flex flex-col relative bg-white/80 backdrop-blur-xl border border-slate-200 shadow-2xl rounded-2xl overflow-hidden">
```
Change input box area (pill shape):
```javascript
{/* Input Composer */}
<div className="p-4 lg:px-6 pb-6 bg-gradient-to-t from-white/90 via-white/80 to-transparent flex-shrink-0">
  <div className="max-w-[820px] mx-auto">
    <div className="mb-3 flex flex-wrap gap-2 px-1">
      {/* ... keep quick actions ... */}
    </div>
    
    <div className="bg-white border border-slate-200 rounded-[28px] shadow-lg p-2.5 flex items-end gap-2 focus-within:border-cyan-400 focus-within:ring-4 focus-within:ring-cyan-500/10 transition-all">
      <div className="flex gap-1 text-slate-400 pb-1 pl-1">
        <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-full transition-colors cursor-pointer flex items-center justify-center">
          <Icon name="attach_file" className="material-symbols-outlined text-[18px]"/>
        </button>
      </div>
      
      <textarea 
        className="flex-1 border-none focus:ring-0 px-2 py-2 text-[14px] text-slate-800 placeholder-slate-400 resize-none outline-none max-h-32 bg-transparent" 
        // ...
      ></textarea>
      
      <div className="flex justify-end items-center px-1 pb-1">
        {/* ... Send button (make it rounded-full instead of rounded-lg) ... */}
        <button className="w-8 h-8 rounded-full bg-cyan-500 text-white flex items-center justify-center ...">
           <Icon name="arrow_upward" className="material-symbols-outlined text-[16px]"/>
        </button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Run lint and tests**
Run: `cd frontend && npm run lint && npm test -- ChatArea.test.jsx`
Fix any broken selectors in tests if they depend on old class names.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/pages/AIChat.jsx frontend/src/components/chat/ChatArea*
git commit -m "style: implement floating ChatArea and pill input layout"
```

---

### Task 4: Modernize ChatMessage Bubbles

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.jsx`

- [ ] **Step 1: Update AI Message styling (borderless document feel)**
In `frontend/src/components/chat/ChatMessage.jsx`:
Change the container padding and background for AI:
```javascript
// For AI: 'text-slate-700 py-1' -> 'text-slate-700 py-2 w-full'
// For User: 'bg-cyan-500 text-white rounded-3xl rounded-tr-sm shadow-md p-3.5 max-w-[85%]'
<div className={`w-full min-w-0 overflow-hidden transition-all ${isUser ? 'bg-cyan-500 text-white rounded-3xl rounded-tr-sm shadow-md p-3.5 max-w-[85%]' : 'text-slate-700 py-2 px-1'}`}>
```

- [ ] **Step 2: Update Avatars**
```javascript
// Avatar container
<div className={`w-8 h-8 flex-shrink-0 flex items-center justify-center mt-1 ${isUser ? 'bg-transparent text-slate-400' : 'rounded-full bg-gradient-to-tr from-cyan-400 to-indigo-400 text-white shadow-sm'}`}>
  {isUser ? (
    // Instead of blue block, maybe just a simple icon or smaller bubble
    <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center text-slate-500"><Icon name="person" className="text-[14px]"/></div>
  ) : (
    <span className="text-[11px] font-bold tracking-wider">AI</span>
  )}
</div>
```

- [ ] **Step 3: Run lint and tests**
Run: `cd frontend && npm run lint && npm test -- ChatMessage.test.jsx`

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/chat/ChatMessage.jsx
git commit -m "style: modernize ChatMessage bubbles and avatars"
```
