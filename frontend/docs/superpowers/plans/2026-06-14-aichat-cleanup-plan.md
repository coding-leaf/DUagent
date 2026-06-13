# AI Chat Mock Data Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the AIChat interface by removing mock resource data, fixing the course name display, and using generalized prompts in the empty state.

**Architecture:** Pure frontend UI modifications within the existing React component tree, adjusting props and static JSX blocks. No backend API calls are added to avoid circumventing the upcoming Agent retrieval verification design.

**Tech Stack:** React, Tailwind CSS

---

### Task 1: Generalize ChatEmptyState Prompts

**Files:**
- Modify: `src/components/chat/ChatEmptyState.jsx`

- [ ] **Step 1: Write the updated component implementation**

```javascript
export default function ChatEmptyState({ onCardClick, courseName = '当前课程' }) {
  const suggestCards = [
    {
      icon: 'lightbulb',
      title: '解释关键概念',
      prompt: `帮我解释${courseName}里的一个核心概念，并给出例子。`,
      color: 'amber'
    },
    {
      icon: 'code_blocks',
      title: '分析代码或思路',
      prompt: `帮我分析一段和${courseName}相关的代码或解题思路。`,
      color: 'emerald'
    },
    {
      icon: 'menu_book',
      title: '推荐学习方向',
      prompt: `请根据${courseName}推荐我接下来应该学习的方向。`,
      color: 'indigo'
    },
    {
      icon: 'calendar_month',
      title: '规划复习安排',
      prompt: `我想复习${courseName}的薄弱点，请帮我规划一周学习安排。`,
      color: 'rose'
    }
  ];

  const getColorClasses = (color) => {
    const classes = {
      amber: 'bg-amber-50 text-amber-600 group-hover:bg-amber-100',
      emerald: 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100',
      indigo: 'bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100',
      rose: 'bg-rose-50 text-rose-600 group-hover:bg-rose-100'
    };
    return classes[color];
  };

  return (
    <div className="h-full flex flex-col items-center justify-center py-10 px-4">
      <div className="w-16 h-16 bg-gradient-to-tr from-cyan-400 to-blue-500 rounded-2xl flex items-center justify-center shadow-lg shadow-cyan-200/50 mb-6 relative">
        <span className="material-symbols-outlined text-[32px] text-white">smart_toy</span>
        <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full border-2 border-white"></div>
      </div>
      
      <h2 className="text-2xl font-bold text-slate-800 mb-2">你好，我是你的智能助教</h2>
      <p className="text-slate-500 mb-10 text-center max-w-md leading-relaxed">
        我可以帮你解答疑惑、分析代码、规划学习路线，或者基于课程资料进行知识拓展。
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-2xl">
        {suggestCards.map((card, idx) => (
          <div 
            key={idx}
            onClick={() => onCardClick(card.prompt)}
            className="group bg-white border border-slate-200 rounded-2xl p-4 cursor-pointer hover:border-cyan-300 hover:shadow-md transition-all duration-300 flex items-start gap-4"
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors ${getColorClasses(card.color)}`}>
              <span className="material-symbols-outlined text-[20px]">{card.icon}</span>
            </div>
            <div>
              <h3 className="font-semibold text-slate-700 text-[15px] mb-1 group-hover:text-cyan-700 transition-colors">{card.title}</h3>
              <p className="text-slate-500 text-[13px] leading-relaxed line-clamp-2">{card.prompt}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run linter to verify syntax**

Run: `npm run lint`
Expected: PASS without errors in ChatEmptyState.jsx

- [ ] **Step 3: Commit**

```bash
git add src/components/chat/ChatEmptyState.jsx
git commit -m "refactor(chat): generalize ChatEmptyState prompts with courseName prop"
```

---

### Task 2: Clean up AIChat Mock Data and Fix Course Name

**Files:**
- Modify: `src/pages/AIChat.jsx`

- [ ] **Step 1: Write the updated component implementation**

Replace the activeCourseName assignment and pass the prop to ChatEmptyState. Also, clear the hardcoded cards in the right sidebar.

First, fix the `activeCourseName` definition near the top:
```javascript
// ... existing imports ...
export default function AIChat() {
// ... inside component ...
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  const activeCourse = courses?.find(c => c.id === activeCourseId);
  const activeCourseName = activeCourse?.name || activeCourse?.title || '未选择课程';
```

Then pass it to `ChatEmptyState`:
```javascript
              {messages.length === 0 ? (
                <ChatEmptyState onCardClick={handleSendMessage} courseName={activeCourseName} />
              ) : (
```

Then completely replace the content of the "Right Sidebar - Resources" element `<aside className="w-72 bg-white border-l border-slate-200 hidden xl:flex flex-col">`:
```javascript
        {/* Right Sidebar - Resources (Competition Ready) */}
        <aside className="w-72 bg-white border-l border-slate-200 hidden xl:flex flex-col">
          <div className="p-5 border-b border-slate-100">
            <div className="text-[11px] font-bold text-slate-400 mb-1">当前学习上下文</div>
            <div className="text-slate-800 font-semibold text-sm truncate" title={activeCourseName}>
              {activeCourseName}
            </div>
          </div>
          
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
        </aside>
```

- [ ] **Step 2: Run linter to verify syntax**

Run: `npm run lint`
Expected: PASS without errors in AIChat.jsx

- [ ] **Step 3: Commit**

```bash
git add src/pages/AIChat.jsx
git commit -m "fix(chat): remove mock resource data and fix active course name fallback"
```
