# AI Chat UI Rearchitecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect the AIChat page to implement a 3-column layout featuring a Left SidebarHistory, a Center AgentWorkspace dynamic component engine, and a Right ChatArea, with mocked interfaces and pluggable components for testing.

**Architecture:** Extend `ChatContext` with a `workspaceArtifacts` state and a Mock helper, build a dynamic component registry with custom plugin types (QuizCard, MermaidViewer, MarkdownViewer), and refactor the AIChat layout and individual sidebars to distribute layout responsibilities cleanly.

**Tech Stack:** React 19, TailwindCSS, SWR, Mermaid.js, React-Markdown.

---

### Task 1: Extend ChatContext & Add Test Helper for Mocking Artifacts

**Files:**
- Modify: `frontend/src/context/ChatContext.jsx`
- Test: `frontend/src/context/ChatContext.test.jsx` (New)

- [ ] **Step 1: Write a failing test for ChatContext workspace state**

Create `frontend/src/context/ChatContext.test.jsx` to test `workspaceArtifacts` initialization and a helper function `triggerMockArtifact` to push simulated payloads.

```jsx
import { render, screen, act } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { ChatProvider, useChat } from './ChatContext';
import { CourseProvider } from './CourseContext';

// Simple consumer to test context value
const TestConsumer = () => {
  const { workspaceArtifacts, sendMockArtifact } = useChat();
  return (
    <div>
      <div data-testid="count">{workspaceArtifacts.length}</div>
      <button data-testid="trigger" onClick={() => sendMockArtifact({ type: 'QuizCard', props: { question: 'Test?' } })}>
        Trigger
      </button>
    </div>
  );
};

test('workspaceArtifacts state manages active workspace plugin payloads', async () => {
  render(
    <CourseProvider>
      <ChatProvider>
        <TestConsumer />
      </ChatProvider>
    </CourseProvider>
  );

  expect(screen.getByTestId('count').textContent).toBe('0');
  
  await act(async () => {
    screen.getByTestId('trigger').click();
  });

  expect(screen.getByTestId('count').textContent).toBe('1');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx`
Expected: FAIL due to missing `workspaceArtifacts` and `sendMockArtifact` in context.

- [ ] **Step 3: Implement workspace state and mock helper in ChatContext.jsx**

Modify `frontend/src/context/ChatContext.jsx` to add the state, expose it in the provider, and implement a mock helper.

```jsx
// 1. Inside ChatProvider component:
const [workspaceArtifacts, setWorkspaceArtifacts] = useState([]);

const sendMockArtifact = (payload) => {
  const newArtifact = {
    id: `artifact-${crypto.randomUUID()}`,
    type: payload.type,
    props: payload.props || {},
    timestamp: new Date().toISOString()
  };
  setWorkspaceArtifacts(prev => [...prev, newArtifact]);
};

// 2. Expose in Context.Provider:
workspaceArtifacts, sendMockArtifact
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/context/ChatContext.jsx frontend/src/context/ChatContext.test.jsx
git commit -m "feat(chat-context): extend chat context with workspace artifacts and mock helpers"
```

---

### Task 2: Create PluginRegistry & Dynamic Render Testing

**Files:**
- Create: `frontend/src/components/workspace/PluginRegistry.js`
- Test: `frontend/src/components/workspace/PluginRegistry.test.js`

- [ ] **Step 1: Write a failing test for PluginRegistry**

Create `frontend/src/components/workspace/PluginRegistry.test.js` to ensure the registry maps string types to valid components.

```javascript
import { expect, test } from 'vitest';
import { PluginRegistry } from './PluginRegistry';

test('PluginRegistry resolves standard component types correctly', () => {
  expect(PluginRegistry.QuizCard).toBeDefined();
  expect(PluginRegistry.Mermaid).toBeDefined();
  expect(PluginRegistry.Markdown).toBeDefined();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:unit -- src/components/workspace/PluginRegistry.test.js`
Expected: FAIL due to missing files.

- [ ] **Step 3: Create registry and stub components**

Create files in `frontend/src/components/workspace/` and `frontend/src/components/workspace/plugins/` to fulfill the registry mapping.

Create `frontend/src/components/workspace/PluginRegistry.js`:
```javascript
import QuizCard from './plugins/QuizCard';
import MermaidViewer from './plugins/MermaidViewer';
import MarkdownViewer from './plugins/MarkdownViewer';

export const PluginRegistry = {
  QuizCard,
  Mermaid: MermaidViewer,
  Markdown: MarkdownViewer
};
```

Create placeholder file `frontend/src/components/workspace/plugins/QuizCard.jsx`:
```jsx
export default function QuizCard() { return <div>QuizCard Stub</div>; }
```

Create placeholder file `frontend/src/components/workspace/plugins/MermaidViewer.jsx`:
```jsx
export default function MermaidViewer() { return <div>MermaidViewer Stub</div>; }
```

Create placeholder file `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`:
```jsx
export default function MarkdownViewer() { return <div>MarkdownViewer Stub</div>; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:unit -- src/components/workspace/PluginRegistry.test.js`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/components/workspace/
git commit -m "feat(workspace): add PluginRegistry and component stubs"
```

---

### Task 3: Build Plugin Components (QuizCard, MermaidViewer, MarkdownViewer)

**Files:**
- Modify: `frontend/src/components/workspace/plugins/QuizCard.jsx`
- Modify: `frontend/src/components/workspace/plugins/MermaidViewer.jsx`
- Modify: `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`

- [ ] **Step 1: Write implementation for QuizCard**

Create a clean interactive quiz question renderer with states for selection and validation feedback.

```jsx
import { useState } from 'react';

export default function QuizCard({ question, choices, correctAnswer }) {
  const [selected, setSelected] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <h3 className="text-slate-800 font-semibold mb-4">{question}</h3>
      <div className="space-y-2">
        {choices.map((choice, idx) => {
          let optionStyle = 'border-slate-200 hover:bg-slate-50 text-slate-700';
          if (submitted) {
            if (idx === correctAnswer) optionStyle = 'bg-green-50 border-green-300 text-green-800';
            else if (selected === idx) optionStyle = 'bg-red-50 border-red-300 text-red-800';
          } else if (selected === idx) {
            optionStyle = 'bg-cyan-50 border-cyan-400 text-cyan-800';
          }
          return (
            <button
              key={idx}
              disabled={submitted}
              onClick={() => setSelected(idx)}
              className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-all cursor-pointer ${optionStyle}`}
            >
              {choice}
            </button>
          );
        })}
      </div>
      <div className="mt-4 flex justify-end">
        <button
          disabled={selected === null || submitted}
          onClick={() => setSubmitted(true)}
          className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer"
        >
          提交答案
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write implementation for MermaidViewer**

Render a dynamic flow chart using the already installed `mermaid` package.

```jsx
import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
});

export default function MermaidViewer({ chart }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current && chart) {
      containerRef.current.innerHTML = chart;
      try {
        mermaid.contentLoaded();
      } catch (err) {
        console.error('Mermaid render error:', err);
      }
    }
  }, [chart]);

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 flex justify-center overflow-x-auto shadow-sm">
      <div ref={containerRef} className="mermaid w-full text-center" />
    </div>
  );
}
```

- [ ] **Step 3: Write implementation for MarkdownViewer**

Reuse `react-markdown` to show interactive lesson content or structured HTML slideshow style notes.

```jsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownViewer({ content }) {
  return (
    <div className="prose prose-slate max-w-none bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 4: Verify syntax & build**

Run: `cd frontend && npm run build`
Expected: Successful compile with no lint or typescript errors.

- [ ] **Step 5: Commit changes**

```bash
git add frontend/src/components/workspace/plugins/
git commit -m "feat(plugins): implement interactive QuizCard, MermaidViewer, and MarkdownViewer plugins"
```

---

### Task 4: Implement AgentWorkspace Container Component

**Files:**
- Create: `frontend/src/components/workspace/AgentWorkspace.jsx`

- [ ] **Step 1: Write AgentWorkspace container**

Create `frontend/src/components/workspace/AgentWorkspace.jsx`. This component loops through `workspaceArtifacts` and renders components from the `PluginRegistry` or displays an empty work surface when no artifacts exist.

```jsx
import { useChat } from '../../context/ChatContext';
import { PluginRegistry } from './PluginRegistry';
import Icon from '../Icon';

export default function AgentWorkspace() {
  const { workspaceArtifacts } = useChat();

  return (
    <div className="flex-1 flex flex-col bg-slate-50 border-r border-slate-200 overflow-y-auto custom-scrollbar p-6">
      <div className="flex items-center gap-2 mb-6 flex-shrink-0">
        <Icon name="design_services" className="material-symbols-outlined text-slate-600 text-[20px]" />
        <h2 className="text-base font-semibold text-slate-800">Agent 工作区</h2>
      </div>

      <div className="flex-1 space-y-6">
        {workspaceArtifacts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
            <Icon name="dashboard_customize" className="material-symbols-outlined text-[48px] mb-3 text-slate-300" />
            <p className="text-sm">暂无生成产物，请在右侧与 AI 互动生成学习路径、卡片或图表</p>
          </div>
        ) : (
          workspaceArtifacts.map((artifact) => {
            const Component = PluginRegistry[artifact.type];
            if (!Component) {
              return (
                <div key={artifact.id} className="p-4 bg-red-50 text-red-800 border border-red-200 rounded-xl text-sm">
                  未知插件类型: {artifact.type}
                </div>
              );
            }
            return (
              <div key={artifact.id} className="transition-all duration-300 transform scale-98 animate-fadeIn">
                <Component {...artifact.props} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify lint & build**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add frontend/src/components/workspace/AgentWorkspace.jsx
git commit -m "feat(workspace): implement AgentWorkspace wrapper component"
```

---

### Task 5: Refactor Layout in AIChat.jsx & Adjust Component Sizing

**Files:**
- Modify: `frontend/src/pages/AIChat.jsx`
- Modify: `frontend/src/components/chat/ChatArea.jsx`
- Modify: `frontend/src/components/chat/SidebarHistory.jsx`

- [ ] **Step 1: Update AIChat.jsx layout**

Modify `frontend/src/pages/AIChat.jsx` to output the new 3-column layout structure: Left (SidebarHistory), Center (AgentWorkspace), Right (ChatArea).

```jsx
// Exact lines 36-66 replacement:
  return (
    <div className="font-body-md text-slate-800 bg-slate-50 h-screen flex flex-col overflow-hidden">
      <Navbar />

      <div className="flex-1 flex overflow-hidden pt-16">
        {/* Left Side: Historical chats */}
        <SidebarHistory 
          leftCollapsed={leftCollapsed}
          leftDrawerOpen={leftDrawerOpen}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
          onCloseDrawer={() => setLeftDrawerOpen(false)}
          onNewChat={handleNewChat}
        />

        {/* Center: Agent Workspace */}
        <AgentWorkspace />

        {/* Right Side: AI Dialogue area */}
        <ChatArea 
          key={activeSession || 'empty'}
          activeCourseName={activeCourseName}
          onOpenLeftDrawer={handleOpenLeftDrawer}
          onOpenRightDrawer={handleOpenRightDrawer}
        />
      </div>
    </div>
  );
```

- [ ] **Step 2: Add CSS adjustment for ChatArea.jsx**

Adjust `ChatArea.jsx` classes to make it render nicely as a narrow sidebar (e.g. limit maximum width to `w-[360px]` on desktop, shrink paddings, keep clean inputs). Add a dev console/mock triggers area at the bottom for testing.

```jsx
// 1. Update overall main wrapper classes in ChatArea.jsx line 45:
<main className="w-full lg:w-[380px] flex flex-col relative bg-white border-l border-slate-200 flex-shrink-0 min-w-0">

// 2. Insert mock generator button helper inside ChatArea input bar area (lines 174-182 area):
<div className="flex justify-between items-center px-1">
  <div className="flex gap-1 text-slate-400">
    <button 
      onClick={() => {
        const mockQuiz = {
          type: 'QuizCard',
          props: {
            question: '数据结构中，以下哪个算法是用于寻找最短路径的？',
            choices: ['A. Prim 算法', 'B. Dijkstra 算法', 'C. Kruskal 算法', 'D. KMP 算法'],
            correctAnswer: 1
          }
        };
        // Expose via debug helper we created in Task 1
        window.dispatchEvent(new CustomEvent('mock-artifact', { detail: mockQuiz }));
      }}
      className="p-1 hover:bg-slate-100 hover:text-cyan-600 rounded text-xs text-cyan-500 font-semibold cursor-pointer border border-cyan-200"
      title="模拟生成测验"
    >
      + 测验卡片
    </button>
    <button 
      onClick={() => {
        const mockMermaid = {
          type: 'Mermaid',
          props: {
            chart: 'graph TD\nA[二叉树] --> B(二叉搜索树)\nA --> C(平衡二叉树)\nC --> D(AVL 树)'
          }
        };
        window.dispatchEvent(new CustomEvent('mock-artifact', { detail: mockMermaid }));
      }}
      className="p-1 hover:bg-slate-100 hover:text-cyan-600 rounded text-xs text-cyan-500 font-semibold cursor-pointer border border-cyan-200"
      title="模拟生成图表"
    >
      + 流程图
    </button>
  </div>
```

- [ ] **Step 3: Connect window events in ChatArea.jsx to context**

Add a `useEffect` inside `ChatArea.jsx` to listen to window mock-artifact event and trigger the context method `sendMockArtifact`.

```javascript
const { sendMockArtifact } = useChat();

useEffect(() => {
  const handler = (e) => {
    sendMockArtifact(e.detail);
  };
  window.addEventListener('mock-artifact', handler);
  return () => window.removeEventListener('mock-artifact', handler);
}, [sendMockArtifact]);
```

- [ ] **Step 4: Update SidebarHistory.jsx and add category filters**

Modify `frontend/src/components/chat/SidebarHistory.jsx` to add filter tags right below the header:

```jsx
// Insert category tag UI under "历史记录" header:
<div className="flex flex-wrap gap-1 px-3 mb-3">
  {['全部', '数据结构', '算法', '计网'].map((tag) => (
    <span key={tag} className="px-2 py-0.5 text-[10px] font-semibold bg-slate-100 text-slate-600 rounded-full hover:bg-cyan-50 hover:text-cyan-600 cursor-pointer">
      {tag}
    </span>
  ))}
</div>
```

- [ ] **Step 5: Verify build & lint**

Run: `cd frontend && npm run lint && npm run build`
Expected: Compilation success with zero errors.

- [ ] **Step 6: Commit changes**

```bash
git add frontend/src/pages/AIChat.jsx frontend/src/components/chat/ChatArea.jsx frontend/src/components/chat/SidebarHistory.jsx
git commit -m "feat(ui): refactor AIChat to 3-column layout and add mock preview actions"
```
