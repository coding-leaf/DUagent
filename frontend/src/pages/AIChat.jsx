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
  const lastMessageIdRef = useRef(null);

  const activeCourse = courses?.find(c => c.id === activeCourseId);
  const activeCourseName = activeCourse?.name || activeCourse?.title || '未选择课程';

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
    lastMessageIdRef.current = null;
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
    lastMessageIdRef.current = null;

    // Optimistic UI updates
    setMessages(prev => {
      const userMsg = { id: `user-${prev.length}`, role: 'user', content: textToSend };
      const aiPlaceholder = { id: 'ai-placeholder', role: 'assistant', content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [], toolCalls: [] };
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
        if (msg.type === 'status') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              const statusText = msg.message || msg.content || '正在处理...';
              return {
                ...m,
                toolCalls: [{ name: statusText, status: 'running' }]
              };
            }
            return m;
          }));
        } else if (msg.type === 'chunk') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              return { ...m, content: m.content + (msg.content || ''), toolCalls: [] };
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
        } else if (msg.type === 'review') {
          const targetId = lastMessageIdRef.current;
          setMessages(prev => {
            const fallbackId = [...prev].reverse().find(m => m.role === 'assistant')?.id;
            const idToFlag = targetId || fallbackId;
            if (!idToFlag) return prev;
            return prev.map(m => (
              m.id === idToFlag
                ? { ...m, reviewFlagged: true, reviewReason: msg.reason || 'off_topic' }
                : m
            ));
          });
        }
      },
      (doneData) => {
        const finalMessageId = doneData.message_id || `ai-${Date.now()}`;
        lastMessageIdRef.current = finalMessageId;
        setMessages(prev => prev.map(m => {
          if (m.id === 'ai-placeholder') {
            return {
              ...m,
              id: finalMessageId,
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
                <ChatEmptyState onCardClick={handleSendMessage} courseName={activeCourseName} />
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

      </div>
    </div>
  );
}
