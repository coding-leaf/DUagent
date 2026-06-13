# AIChat Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the AIChat interface into a professional, 3-column learning workspace with refined message typography and a functional empty state.

**Architecture:** We will implement the design specified in `docs/superpowers/specs/2026-06-14-aichat-redesign-design.md`. The work involves updating styling in `ToolCallCard.jsx` and `ChatMessage.jsx`, creating a new `ChatEmptyState.jsx` component, and finally restructuring the layout in `AIChat.jsx`.

**Tech Stack:** React, Tailwind CSS

---

### Task 1: Refactor ToolCallCard

**Files:**
- Modify: `src/components/chat/ToolCallCard.jsx`

- [ ] **Step 1: Write the updated ToolCallCard implementation**

```javascript
import { useState } from 'react';

export default function ToolCallCard({ name, status, details }) {
  const isRunning = status === 'running';

  return (
    <div className="flex items-center gap-2 text-slate-500 text-[13px] mb-3">
      {isRunning ? (
        <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-slate-300 border-t-slate-500 animate-spin"></span>
      ) : (
        <span className="material-symbols-outlined text-[16px] text-emerald-500">check_circle</span>
      )}
      <span>{name || '正在检索知识库...'}</span>
    </div>
  );
}
```

- [ ] **Step 2: Run linter to verify syntax**

Run: `npm run lint`
Expected: PASS without errors in ToolCallCard.jsx

- [ ] **Step 3: Commit**

```bash
git add src/components/chat/ToolCallCard.jsx
git commit -m "style(chat): update ToolCallCard to minimal inline indicator"
```

### Task 2: Refactor ChatMessage for Document-Style

**Files:**
- Modify: `src/components/chat/ChatMessage.jsx`

- [ ] **Step 1: Update ChatMessage UI**

Update the component to remove the card bubble for the AI, adjusting padding, line-height, and tag styling.

```javascript
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ToolCallCard from './ToolCallCard';

const getDisplayText = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.code || value.name || value.title || value.content || JSON.stringify(value);
  }
  return String(value);
};

export default function ChatMessage({ message, onSendMessage }) {
  const isUser = message.role === 'user';
  
  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className={`flex gap-4 max-w-[100%] group ${isUser ? 'ml-auto flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center mt-1 ${isUser ? 'bg-cyan-600 text-white shadow-sm' : 'bg-sky-100 text-cyan-600'}`}>
        {isUser ? (
          <span className="material-symbols-outlined text-[18px]">person</span>
        ) : (
          <span className="text-[12px] font-bold">AI</span>
        )}
      </div>
      
      <div className={`w-full transition-all ${isUser ? 'bg-cyan-600 text-white rounded-2xl rounded-tr-none shadow-md p-4 max-w-[85%]' : 'text-slate-700 py-1'}`}>
        
        {/* Tool Calls */}
        {!isUser && message.toolCalls && message.toolCalls.map((tc, idx) => (
          <ToolCallCard key={idx} name={tc.name} status={tc.status} details={tc.details} />
        ))}

        {/* Markdown Content */}
        <div className={`markdown-body break-words leading-[1.7] ${isUser ? 'text-white' : 'text-slate-700 text-[15px]'}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({inline, className, children, ...props}) {
                const match = /language-(\w+)/.exec(className || '');
                const codeStr = String(children).replace(/\n$/, '');
                return !inline && match ? (
                  <div className="relative rounded-xl overflow-hidden my-4 group/code shadow-sm border border-slate-200">
                    <div className="flex items-center justify-between px-4 py-2 bg-slate-50 text-slate-500 text-[11px] font-mono uppercase tracking-wider border-b border-slate-200">
                      <span>{match[1]}</span>
                      <button 
                        onClick={() => handleCopy(codeStr)}
                        className="opacity-0 group-hover/code:opacity-100 transition-opacity hover:text-slate-700 flex items-center gap-1 cursor-pointer"
                        title="Copy code"
                      >
                        <span className="material-symbols-outlined text-[14px]">content_copy</span>
                        Copy
                      </button>
                    </div>
                    <SyntaxHighlighter
                      {...props}
                      children={codeStr}
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      customStyle={{ margin: 0, padding: '1rem', borderTopLeftRadius: 0, borderTopRightRadius: 0, fontSize: '13px', lineHeight: '1.5' }}
                    />
                  </div>
                ) : (
                  <code {...props} className={`${className} bg-slate-100 text-cyan-700 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-200`}>
                    {children}
                  </code>
                );
              }
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Loading Indicator */}
        {message.loading && message.content === '' && (
          <div className="flex items-center gap-1.5 text-cyan-500 h-6 pl-1 mt-2">
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
          </div>
        )}

        {/* Error message */}
        {message.isError && (
          <div className="mt-2 text-red-500 text-[13px] flex items-center gap-1 font-medium bg-red-50 p-2 rounded-lg w-fit">
            <span className="material-symbols-outlined text-[16px]">error</span>
            {message.content.includes('发送失败') ? '' : '生成失败，请重试'}
          </div>
        )}

        {/* Diagrams */}
        {!isUser && message.diagrams && message.diagrams.map((diag, index) => (
          <div key={`diagram-${index}`} className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm">
            <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
              <span className="material-symbols-outlined text-[16px] text-cyan-600">schema</span>
              <span>图解模式 (Mermaid)</span>
            </div>
            <pre className="text-[13px] font-mono bg-[#1E1E1E] text-slate-100 p-4 rounded-lg overflow-x-auto whitespace-pre border border-slate-800 leading-relaxed">
              {getDisplayText(diag)}
            </pre>
          </div>
        ))}

        {/* Suggestions */}
        {!isUser && message.suggestions && message.suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-slate-100">
            {message.suggestions.map((sug, i) => (
              <button
                key={`suggestion-${i}`}
                onClick={() => onSendMessage(sug)} 
                className="px-3 py-1.5 bg-white text-slate-600 text-[13px] rounded-lg cursor-pointer hover:bg-slate-50 transition-all border border-slate-200 shadow-sm flex items-center gap-1.5 active:scale-95"
              >
                <span className="material-symbols-outlined text-[14px] text-cyan-500">lightbulb</span>
                {sug}
              </button>
            ))}
          </div>
        )}

        {/* Knowledge Points */}
        {!isUser && message.knowledge_points && message.knowledge_points.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 items-center">
            {message.knowledge_points.map((kp, i) => (
              <span key={`kp-${i}`} className="px-2.5 py-1 bg-slate-100 text-slate-600 text-[12px] rounded-md font-medium">
                # {kp}
              </span>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run linter**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/components/chat/ChatMessage.jsx
git commit -m "style(chat): update ChatMessage to document-style typography"
```

### Task 3: Create ChatEmptyState Component

**Files:**
- Create: `src/components/chat/ChatEmptyState.jsx`

- [ ] **Step 1: Write ChatEmptyState component**

```javascript
export default function ChatEmptyState({ onCardClick }) {
  const cards = [
    {
      icon: '📖',
      title: '解释知识点',
      desc: '“帮我解释C语言指针和数组的关系”',
      query: '帮我解释C语言指针和数组的关系'
    },
    {
      icon: '💻',
      title: '分析代码',
      desc: '“帮我分析这段代码为什么会段错误”',
      query: '帮我分析这段代码为什么会段错误'
    },
    {
      icon: '📚',
      title: '推荐资源',
      desc: '“给我推荐适合复习指针的学习资料”',
      query: '给我推荐适合复习指针的学习资料'
    },
    {
      icon: '🎯',
      title: '规划复习',
      desc: '“我想一周内补齐动态内存分配”',
      query: '我想一周内补齐动态内存分配'
    }
  ];

  return (
    <div className="max-w-[680px] mx-auto mb-10 mt-10 text-center">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">有什么我可以帮你的吗？</h2>
      <p className="text-slate-500 text-sm mb-6">探索本课程的内容，或直接向我提问。</p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {cards.map((card, idx) => (
          <div 
            key={idx}
            onClick={() => onCardClick(card.query)}
            className="bg-white border border-slate-200 p-4 rounded-xl text-left cursor-pointer hover:border-cyan-300 hover:shadow-sm transition-all"
          >
            <div className="font-semibold text-slate-700 text-sm mb-1">
              {card.icon} {card.title}
            </div>
            <div className="text-slate-400 text-xs">
              {card.desc}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run linter**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/components/chat/ChatEmptyState.jsx
git commit -m "feat(chat): add ChatEmptyState with 4 scenario cards"
```

### Task 4: Refactor AIChat Layout

**Files:**
- Modify: `src/pages/AIChat.jsx`

- [ ] **Step 1: Rewrite AIChat.jsx for 3-Column Layout**

Replace the entire file content.

```javascript
import { useState, useEffect, useRef } from 'react';
import { chatService } from '../api/services/chat';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import ChatMessage from '../components/chat/ChatMessage';
import ChatEmptyState from '../components/chat/ChatEmptyState';

const getDisplayText = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.name
      || value.title
      || value.knowledge_point
      || value.label
      || value.content
      || value.id
      || JSON.stringify(value);
  }
  return String(value);
};

const normalizeTextList = (value) => {
  const list = Array.isArray(value) ? value : [value];
  return list
    .map(getDisplayText)
    .map(item => item.trim())
    .filter(Boolean);
};

const normalizeMessage = (message, index = 0) => {
  const normalizedId = message?.id
    || message?.message_id
    || `${message?.role || 'message'}-${message?.timestamp || index}`;

  return {
    ...message,
    id: normalizedId,
    content: getDisplayText(message?.content),
    diagrams: Array.isArray(message?.diagrams) ? message.diagrams : [],
    knowledge_points: normalizeTextList(message?.knowledge_points),
    suggestions: normalizeTextList(message?.suggestions),
  };
};

const normalizeMessages = (items) => (
  Array.isArray(items) ? items.map(normalizeMessage) : []
);

export default function AIChat() {
  const { activeCourseId, courses } = useCourse();
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  const activeCourseName = courses?.find(c => c.id === activeCourseId)?.title || '未选择课程';

  // Sync sessions list when course changes
  useEffect(() => {
    if (activeCourseId) {
      chatService.getSessions(activeCourseId).then(res => {
        if (res.code === 200 && res.data) {
          const list = res.data.conversations || res.data;
          setSessions(list);
          if (list.length > 0) {
            setActiveSession(list[0].id);
          } else {
            setActiveSession(null);
            setTimeout(() => setMessages([]), 0);
          }
        }
      }).catch(console.error);
    }
  }, [activeCourseId]);

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

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current();
      }
    };
  }, []);

  const handleResetConversation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
    setActiveSession(null);
    setMessages([]);
    setIsSending(false);
  };

  const handleSendMessage = (overrideText = '') => {
    const textToSend = (overrideText || inputValue).trim();
    if (!textToSend || isSending || !activeCourseId) return;

    if (!overrideText) {
      setInputValue('');
    }

    if (abortControllerRef.current) {
      abortControllerRef.current();
    }

    // Optimistic UI updates
    setMessages(prev => {
      const userMsg = { id: `user-${prev.length}`, role: 'user', content: textToSend };
      const aiPlaceholder = { id: 'ai-placeholder', role: 'assistant', content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [] };
      return [...prev, userMsg, aiPlaceholder];
    });
    setIsSending(true);
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);

    abortControllerRef.current = chatService.streamChat(
      {
        message: textToSend,
        scope: 'course',
        course_id: activeCourseId,
        conversation_id: activeSession
      },
      (msg) => {
        if (msg.type === 'chunk') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              return { ...m, content: m.content + (msg.content || '') };
            }
            return m;
          }));
          setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
        } else if (msg.type === 'diagram') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              const currentDiags = m.diagrams || [];
              const newDiag = msg.data || msg.content;
              return { ...m, diagrams: [...currentDiags, newDiag] };
            }
            return m;
          }));
        } else if (msg.type === 'knowledge_points') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              const rawPoints = msg.knowledge_points || msg.points || msg.data || [];
              const parsedPoints = normalizeTextList(rawPoints);
              return { ...m, knowledge_points: parsedPoints };
            }
            return m;
          }));
        } else if (msg.type === 'suggestion') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              const currentSugs = m.suggestions || [];
              const newSugs = msg.data || msg.content || [];
              const combined = normalizeTextList(newSugs);
              return { ...m, suggestions: [...currentSugs, ...combined] };
            }
            return m;
          }));
        }
      },
      (doneData) => {
        setMessages(prev => prev.map(m => {
          if (m.id === 'ai-placeholder') {
            return {
              ...m,
              id: doneData.message_id || `ai-${prev.length}`,
              loading: false
            };
          }
          return m;
        }));
        setIsSending(false);
        abortControllerRef.current = null;

        if (!activeSession && doneData.conversation_id) {
          setActiveSession(doneData.conversation_id);
          chatService.getSessions(activeCourseId).then(res => {
            if (res.code === 200 && res.data) {
              setSessions(res.data.conversations || res.data);
            }
          }).catch(console.error);
        }
      },
      (err) => {
        setMessages(prev => prev.map(m => {
          if (m.id === 'ai-placeholder') {
            return {
              ...m,
              content: m.content + '\n\n[发送失败: ' + (err.message || '网络连接故障') + ']',
              loading: false,
              isError: true
            };
          }
          return m;
        }));
        setIsSending(false);
        abortControllerRef.current = null;
      }
    );
  };

  return (
    <div className="font-body-md text-slate-800 bg-slate-50 min-h-screen flex flex-col">
      <Navbar />

      <div className="flex-1 flex overflow-hidden pt-16">
        
        {/* Left Sidebar - History */}
        <aside className="w-64 bg-white border-r border-slate-200 flex flex-col hidden lg:flex">
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2 font-bold text-slate-800">
              <div className="w-6 h-6 bg-cyan-500 rounded text-white flex items-center justify-center text-[10px]">AI</div>
              智能学习助手
            </div>
            <button 
              onClick={handleResetConversation}
              className="text-cyan-600 hover:bg-cyan-50 p-1.5 rounded-lg transition-colors cursor-pointer"
              title="新对话"
            >
              <span className="material-symbols-outlined text-[18px]">add</span>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
            <div className="px-3 py-2 text-xs font-bold text-slate-400 mb-1">历史记录</div>
            {sessions.map(session => (
              <div 
                key={session.id} 
                onClick={() => {
                  if (abortControllerRef.current) {
                    abortControllerRef.current();
                    abortControllerRef.current = null;
                  }
                  setActiveSession(session.id);
                }}
                className={`px-3 py-2 rounded-lg cursor-pointer text-[13px] truncate transition-colors ${
                  activeSession === session.id 
                    ? 'bg-slate-100 text-slate-800 font-semibold' 
                    : 'text-slate-500 hover:bg-slate-50'
                }`}
              >
                {session.title}
              </div>
            ))}
            {sessions.length === 0 && (
              <p className="text-xs text-slate-400 px-3 py-4">无历史对话</p>
            )}
          </div>
        </aside>

        {/* Center Column - Main Chat */}
        <main className="flex-1 flex flex-col relative bg-slate-50">
          
          {/* Top Context Bar */}
          <div className="h-14 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 z-10">
            <div className="text-sm text-slate-700 font-medium truncate">
              {activeSession ? sessions.find(s => s.id === activeSession)?.title || '对话中' : '新对话'}
            </div>
          </div>

          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto custom-scrollbar px-4 lg:px-8 py-8">
            <div className="max-w-[760px] mx-auto space-y-8 pb-4">
              
              {messages.length === 0 ? (
                <ChatEmptyState onCardClick={handleSendMessage} />
              ) : (
                messages.map(msg => (
                  <ChatMessage key={msg.id} message={msg} onSendMessage={handleSendMessage} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input Composer (Anchored to bottom of middle column) */}
          <div className="p-4 lg:px-8 pb-6 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent">
            <div className="max-w-[760px] mx-auto">
              <div className="bg-white border border-slate-300 rounded-2xl shadow-sm p-3 flex flex-col gap-2 focus-within:border-cyan-400 focus-within:ring-2 focus-within:ring-cyan-100 transition-all">
                <textarea 
                  className="w-full border-none focus:ring-0 px-2 py-1 text-[15px] text-slate-800 placeholder-slate-400 resize-none outline-none max-h-32" 
                  placeholder="在这里输入你的问题..." 
                  rows={1}
                  value={inputValue}
                  onChange={e => {
                    setInputValue(e.target.value);
                    e.target.style.height = 'auto';
                    e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px';
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                ></textarea>
                
                <div className="flex justify-between items-center px-1">
                  <div className="flex gap-1 text-slate-400">
                    <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-lg transition-colors cursor-pointer flex items-center justify-center">
                      <span className="material-symbols-outlined text-[18px]">attach_file</span>
                    </button>
                    <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-lg transition-colors cursor-pointer flex items-center justify-center">
                      <span className="material-symbols-outlined text-[18px]">mic</span>
                    </button>
                  </div>
                  
                  <button 
                    onClick={() => handleSendMessage()}
                    disabled={isSending || !inputValue.trim() || !activeCourseId}
                    className="w-8 h-8 rounded-lg bg-cyan-500 text-white flex items-center justify-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-600 active:scale-95 transition-all shadow-sm"
                  >
                    <span className="material-symbols-outlined text-[16px]">arrow_upward</span>
                  </button>
                </div>
              </div>
              <div className="text-center mt-2 text-[11px] text-slate-400">
                AI 生成内容仅供学习参考
              </div>
            </div>
          </div>
        </main>

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
            
            {/* Placeholder Resource Cards */}
            <div className="border border-slate-200 rounded-xl p-3 bg-white mb-3 hover:shadow-sm transition-shadow cursor-pointer">
              <div className="w-full h-16 bg-slate-100 rounded-md mb-2 flex items-center justify-center text-slate-300">
                <span className="material-symbols-outlined text-2xl">smart_display</span>
              </div>
              <div className="text-[13px] font-semibold text-slate-700 mb-1 leading-tight">深入理解指针内存模型</div>
              <div className="text-[11px] text-slate-500">视频课程 · 15分钟</div>
            </div>
            
            <div className="border border-slate-200 rounded-xl p-3 bg-white hover:shadow-sm transition-shadow cursor-pointer">
              <div className="text-[13px] font-semibold text-slate-700 mb-1 leading-tight">C语言核心代码片段</div>
              <div className="text-[11px] text-slate-500">图文资料 · 必读</div>
            </div>
            
          </div>
        </aside>

      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run build to verify overall compilation**

Run: `npm run build`
Expected: Build passes without compilation errors.

- [ ] **Step 3: Commit**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat(chat): implement 3-column layout and integrate EmptyState"
```

### Review and Polish
Once the steps above are implemented, the UI will be fully migrated to the new design. No additional backend changes are needed as the message objects structure matches what `ChatMessage` expects.
