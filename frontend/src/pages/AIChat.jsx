import { useState, useEffect, useRef } from 'react';
import { chatService } from '../api/services/chat';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';

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
  const { activeCourseId } = useCourse();
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);

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

    // Optimistic UI updates using pure functions
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

        // If it was a new conversation, fetch the new ID and refresh sessions
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
    <div className="font-body-md text-on-background bg-background min-h-screen">
      <Navbar />

      {/* Sidebar specific for Chat */}
      <aside className="h-full w-64 fixed left-0 top-16 bg-white border-r border-gray-100 flex flex-col py-6 space-y-2 font-['Public_Sans'] text-sm hidden lg:flex z-40">
        <div className="px-6 mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-cyan-100 flex items-center justify-center text-cyan-600">
              <span className="material-symbols-outlined">smart_toy</span>
            </div>
            <div>
              <h3 className="font-bold text-on-surface">数据结构掌控者</h3>
              <p className="text-xs text-gray-500">多智能体学习系统</p>
            </div>
          </div>
          <button 
            onClick={handleResetConversation} 
            className="w-full mt-4 bg-primary-container text-on-primary-container py-2 rounded-lg font-semibold active:scale-95 transition-all cursor-pointer hover:opacity-90"
          >
            启动新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 space-y-1">
          <div className="px-2 py-1 text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">历史记录</div>
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
              className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer hover:pl-4 transition-all duration-200 ${activeSession === session.id ? 'bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500 font-medium' : 'text-gray-500 hover:bg-gray-50'}`}
            >
              <span className="material-symbols-outlined">chat</span>
              <span className="truncate">{session.title}</span>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="text-xs text-gray-400 px-2 py-4">无历史对话</p>
          )}
        </div>
      </aside>

      {/* Main Content Stage */}
      <main className="flex-1 ml-0 lg:ml-64 relative pt-16">
        <div className="max-w-[1280px] mx-auto p-6 md:p-8 h-[calc(100vh-64px)] flex flex-col">
          
          {/* Chat Header */}
          <div className="flex items-center justify-between mb-6 bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex-shrink-0 mt-4">
            <div className="flex items-center gap-4">
              <div className="relative">
                <img 
                  alt="DS智能体" 
                  className="w-12 h-12 rounded-full object-cover" 
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuDTph4R2THjMqqQ8MYqgdOtqxa_oTri5CZ4iJbFSWdAtv48LpkFLOYc8xXPnYnHwNOFDZ_vkxfyQPWbffAqdpt6eqSVz1_ygfVV_65KDuJaeSfeZV6QjTw8ixTuU7jV5iOpqGHUUT0MmW-Lnd3SV78coSR4hC-RXUedoJ6yz5DuzRycn9WZHzGXsO4FML2jIwNVguUis_bKXa6hIs9A53YZ5vjZvMl5Utsm9Y3sMvpBO1gyZRyQKW8hOX97tXNqahu4iUD5K0CjvZCG" 
                />
                <span className="absolute bottom-0 right-0 w-3 h-3 bg-emerald-400 border-2 border-white rounded-full"></span>
              </div>
              <div>
                <h2 className="font-h3 text-on-surface">DS 智能答疑专家</h2>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-cyan-50 text-cyan-600 text-[10px] rounded-full font-bold">运行中</span>
                  <span className="text-xs text-gray-400">已就绪，随时为您解析复杂结构</span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <button 
                onClick={handleResetConversation}
                className="flex items-center gap-1 px-4 py-2 text-cyan-600 border border-cyan-200 rounded-lg hover:bg-cyan-50 transition-all text-[13px] font-medium cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">refresh</span>
                重置对话
              </button>
            </div>
          </div>

          {/* Chat Scroll Area */}
          <div className="flex-1 overflow-y-auto space-y-6 pb-32 px-2 custom-scrollbar">
            
            {messages.map(msg => (
              <div key={msg.id} className={`flex gap-4 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center ${msg.role === 'user' ? 'bg-cyan-600 text-white' : 'bg-cyan-100 text-cyan-600'}`}>
                  <span className="material-symbols-outlined text-sm" style={msg.role !== 'user' ? { fontVariationSettings: '"FILL" 1' } : {}}>
                    {msg.role === 'user' ? 'person' : 'smart_toy'}
                  </span>
                </div>
                <div className={`p-4 rounded-2xl w-full ${msg.role === 'user' ? 'bg-cyan-600 text-white rounded-tr-none shadow-sm' : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none shadow-sm'}`}>
                  <p className="text-body-md whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  
                  {/* Suggestions rendering */}
                  {msg.suggestions && msg.suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-gray-100">
                      {msg.suggestions.map((sug, i) => (
                        <span
                          key={`${msg.id}-suggestion-${i}-${sug}`}
                          onClick={() => handleSendMessage(sug)} 
                          className="px-3 py-1 bg-gray-50 text-cyan-600 text-xs rounded-full cursor-pointer hover:bg-cyan-50 transition-colors border border-gray-100"
                        >
                          {sug}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Knowledge Points Badges */}
                  {msg.knowledge_points && msg.knowledge_points.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-gray-100">
                      <span className="text-xs text-gray-400 flex items-center gap-1 mr-1">
                        <span className="material-symbols-outlined text-[14px]">school</span>
                        关联知识点:
                      </span>
                      {msg.knowledge_points.map((kp, i) => (
                        <span key={`${msg.id}-knowledge-${i}-${kp}`} className="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] rounded-full font-medium">
                          {kp}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Diagrams rendering */}
                  {msg.diagrams && msg.diagrams.map((diag, index) => (
                    <div key={`${msg.id}-diagram-${index}-${getDisplayText(diag).slice(0, 32)}`} className="bg-gray-50 rounded-xl p-4 border border-gray-200 mt-4 mb-4">
                      <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
                        <span className="material-symbols-outlined text-sm">schema</span>
                        <span>图解模式 (Mermaid)</span>
                      </div>
                      <pre className="text-xs font-mono bg-slate-900 text-slate-100 p-3 rounded-lg overflow-x-auto whitespace-pre">
                        {typeof diag === 'object' ? diag.code || JSON.stringify(diag) : diag}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            
            {isSending && messages.length > 0 && messages[messages.length - 1].loading && messages[messages.length - 1].content === '' && (
               <div className="flex gap-4 max-w-[85%]">
                 <div className="w-8 h-8 rounded-full bg-cyan-100 flex-shrink-0 flex items-center justify-center">
                   <span className="material-symbols-outlined text-cyan-600 text-sm" style={{ fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
                 </div>
                 <div className="bg-white p-4 border border-gray-100 rounded-2xl rounded-tl-none w-16 flex justify-center items-center shadow-sm">
                   <span className="material-symbols-outlined animate-spin text-cyan-600">progress_activity</span>
                 </div>
               </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Anchor */}
          <div className="fixed bottom-4 left-4 lg:left-[280px] right-4 max-w-[1280px] xl:mx-auto bg-background pb-2 pt-2 px-4">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-2 flex items-end gap-2">
              <button className="p-3 text-gray-400 hover:text-cyan-500 transition-all cursor-pointer">
                <span className="material-symbols-outlined">attach_file</span>
              </button>
              <div className="flex-1 min-h-[48px] max-h-32 overflow-y-auto px-2 py-3">
                <textarea 
                  className="w-full border-none focus:ring-0 p-0 text-body-md placeholder-gray-400 resize-none outline-none" 
                  placeholder="在这里输入你的问题，或者输入 / 呼唤特定智能体..." 
                  rows={1}
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                ></textarea>
              </div>
              <div className="flex items-center gap-2 pr-2 pb-1">
                <button className="p-2 text-gray-400 hover:bg-gray-50 rounded-lg cursor-pointer">
                  <span className="material-symbols-outlined">mic</span>
                </button>
                <button 
                  onClick={() => handleSendMessage()}
                  disabled={isSending || !inputValue.trim() || !activeCourseId}
                  className="bg-cyan-600 text-white disabled:opacity-50 w-10 h-10 rounded-xl flex items-center justify-center shadow-md active:scale-90 transition-all cursor-pointer hover:bg-cyan-700"
                >
                  <span className="material-symbols-outlined">send</span>
                </button>
              </div>
            </div>
            <div className="text-center mt-3">
              <p className="text-[10px] text-gray-400 tracking-wide uppercase">AI 生成内容仅供学习参考，请核对关键代码逻辑</p>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
