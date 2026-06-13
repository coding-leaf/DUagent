import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { chatService } from '../api/services/chat';
import { learningService } from '../api/services/learning';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import ChatMessage from '../components/chat/ChatMessage';
import ChatEmptyState from '../components/chat/ChatEmptyState';

const getDisplayText = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    if (value.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(value);
        if (parsed.model_text || parsed.content) {
          return parsed.model_text || parsed.content;
        }
      } catch {
        // Ignored
      }
    }
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.model_text
      || value.name
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

  let contentObj = message?.content;
  if (typeof contentObj === 'string' && contentObj.trim().startsWith('{')) {
    try {
      contentObj = JSON.parse(contentObj);
    } catch {
      // Ignored
    }
  }

  let displayContent;
  let diagrams = message?.diagrams || [];
  let knowledge_points = message?.knowledge_points || [];
  let suggestions = message?.suggestions || [];

  if (typeof contentObj === 'object' && contentObj !== null) {
    displayContent = contentObj.model_text || contentObj.content || JSON.stringify(contentObj);
    if (contentObj.diagram && !diagrams.length) diagrams = [contentObj.diagram];
    if (contentObj.diagrams && !diagrams.length) diagrams = contentObj.diagrams;
    if (contentObj.knowledge_points && !knowledge_points.length) knowledge_points = contentObj.knowledge_points;
    if (contentObj.suggestion && !suggestions.length) suggestions = [contentObj.suggestion];
    if (contentObj.suggestions && !suggestions.length) suggestions = contentObj.suggestions;
  } else {
    displayContent = getDisplayText(message?.content);
  }

  return {
    ...message,
    id: normalizedId,
    content: displayContent,
    diagrams: Array.isArray(diagrams) ? diagrams : (diagrams ? [diagrams] : []),
    knowledge_points: normalizeTextList(knowledge_points),
    suggestions: normalizeTextList(suggestions),
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
  const [resources, setResources] = useState([]);
  
  // Collapse & Drawer States
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
  
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

  // Fetch course resources when activeCourseId changes
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
      setTimeout(() => setResources([]), 0);
    }
  }, [activeCourseId]);

  const handleResetConversation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
    setActiveSession(null);
    lastMessageIdRef.current = null;
    setMessages([]);
    setIsSending(false);
    setLeftDrawerOpen(false); // Close mobile drawer
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
              if (msg.stage === 'generation') {
                const updatedToolCalls = (m.toolCalls || []).map(tc =>
                  tc.id === 'retrieval' ? { ...tc, status: 'completed' } : tc
                );
                return {
                  ...m,
                  toolCalls: updatedToolCalls
                };
              } else if (msg.stage === 'retrieval') {
                return {
                  ...m,
                  toolCalls: [{ id: 'retrieval', name: '检索课程知识库', status: 'running' }]
                };
              }
              const statusText = msg.message || msg.content || '正在处理...';
              return {
                ...m,
                toolCalls: [{ id: 'generic', name: statusText, status: 'running' }]
              };
            }
            return m;
          }));
        } else if (msg.type === 'chunk') {
          setMessages(prev => prev.map(m => {
            if (m.id === 'ai-placeholder') {
              const updatedToolCalls = (m.toolCalls || []).map(tc =>
                tc.status === 'running' ? { ...tc, status: 'completed' } : tc
              );
              return { ...m, content: m.content + (msg.content || ''), toolCalls: updatedToolCalls };
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
            const updatedToolCalls = (m.toolCalls || []).map(tc =>
              tc.status === 'running' ? { ...tc, status: 'completed' } : tc
            );
            return {
              ...m,
              id: finalMessageId,
              loading: false,
              toolCalls: updatedToolCalls
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
            const updatedToolCalls = (m.toolCalls || []).map(tc =>
              tc.status === 'running' ? { ...tc, status: 'completed' } : tc
            );
            return {
              ...m,
              content: m.content + '\n\n[发送失败: ' + (err.message || '网络连接故障') + ']',
              loading: false,
              isError: true,
              toolCalls: updatedToolCalls
            };
          }
          return m;
        }));
        setIsSending(false);
        abortControllerRef.current = null;
      }
    );
  };

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

  return (
    <div className="font-body-md text-slate-800 bg-slate-50 h-screen flex flex-col overflow-hidden">
      <Navbar />

      <div className="flex-1 flex overflow-hidden pt-16">
        
        {/* Left Sidebar - History */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-full
          ${leftDrawerOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          /* Desktop Collapse Style */
          ${leftCollapsed ? 'lg:w-0 lg:opacity-0 lg:overflow-hidden lg:border-transparent' : 'lg:w-64 lg:opacity-100 lg:border-r lg:border-slate-200'}
        `}>
          <div className="flex-1 flex flex-col min-w-[256px] h-full">
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
                    setLeftDrawerOpen(false); // Close mobile history drawer
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
          </div>

          {/* Desktop Collapse Handle */}
          <button 
            onClick={() => setLeftCollapsed(!leftCollapsed)}
            className="hidden lg:flex absolute right-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
            title={leftCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            <span className="material-symbols-outlined text-[16px] select-none">
              {leftCollapsed ? 'chevron_right' : 'chevron_left'}
            </span>
          </button>
        </aside>

        {/* Backdrop Overlay for mobile drawers */}
        {(leftDrawerOpen || rightDrawerOpen) && (
          <div 
            onClick={() => { setLeftDrawerOpen(false); setRightDrawerOpen(false); }}
            className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden transition-opacity duration-300"
          />
        )}

        {/* Center Column - Main Chat */}
        <main className="flex-1 flex flex-col relative bg-slate-50">
          
          {/* Top Context Bar */}
          <div className="h-14 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 z-10">
            <div className="flex items-center gap-1.5 min-w-0">
              {/* Mobile Left Drawer Trigger */}
              <button 
                onClick={() => setLeftDrawerOpen(true)}
                className="lg:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer mr-1 flex items-center justify-center"
                title="打开历史记录"
              >
                <span className="material-symbols-outlined text-[20px]">menu</span>
              </button>
              
              <div className="text-sm text-slate-700 font-medium truncate">
                {activeSession ? sessions.find(s => s.id === activeSession)?.title || '对话中' : '新对话'}
              </div>
            </div>

            {/* Mobile Right Drawer Trigger */}
            <button 
              onClick={() => setRightDrawerOpen(true)}
              className="xl:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer flex items-center justify-center"
              title="查看推荐资源"
            >
              <span className="material-symbols-outlined text-[20px]">menu_book</span>
            </button>
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
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-full
          ${rightDrawerOpen ? 'translate-x-0' : 'translate-x-full xl:translate-x-0'}
          /* Desktop Collapse Style */
          ${rightCollapsed ? 'xl:w-0 xl:opacity-0 xl:overflow-hidden xl:border-transparent' : 'xl:w-72 xl:opacity-100 xl:border-l xl:border-slate-200'}
        `}>
          <div className="flex-1 flex flex-col min-w-[288px] h-full">
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
              
              {recommendedResources.length > 0 ? (
                <div className="space-y-3">
                  {recommendedResources.map(res => {
                    let icon = 'description';
                    let iconBg = 'bg-blue-50 text-blue-600';
                    if (res.type === 'mindmap') {
                      icon = 'hub';
                      iconBg = 'bg-purple-50 text-purple-600';
                    } else if (res.type === 'reading') {
                      icon = 'menu_book';
                      iconBg = 'bg-amber-50 text-amber-600';
                    } else if (res.type === 'code') {
                      icon = 'code';
                      iconBg = 'bg-emerald-50 text-emerald-600';
                    } else if (res.type === 'video') {
                      icon = 'video_library';
                      iconBg = 'bg-rose-50 text-rose-600';
                    }
                    return (
                      <Link 
                        key={res.id} 
                        to={"/resource/" + res.id} 
                        className="flex gap-3 p-3 rounded-xl border border-slate-100 hover:border-cyan-200 hover:bg-cyan-50/30 transition-all duration-200 group cursor-pointer block"
                      >
                        <div className={`w-9 h-9 rounded-lg ${iconBg} flex items-center justify-center flex-shrink-0 font-medium`}>
                          <span className="material-symbols-outlined text-[20px]">{icon}</span>
                        </div>
                        <div className="min-w-0 flex-1">
                          <h4 className="text-[13px] font-semibold text-slate-800 group-hover:text-cyan-700 transition-colors line-clamp-1 mb-0.5">
                            {res.title}
                          </h4>
                          {res.description && (
                            <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                              {res.description}
                            </p>
                          )}
                          {res.knowledge_point && (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              <span className="inline-block px-1.5 py-0.5 text-[9px] font-medium bg-slate-100 text-slate-600 rounded">
                                {res.knowledge_point}
                              </span>
                            </div>
                          )}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              ) : (
                /* Empty State */
                <div className="border border-slate-200 border-dashed rounded-xl p-4 bg-slate-50 flex flex-col items-center justify-center text-center mt-6">
                  <div className="w-12 h-12 bg-slate-100 rounded-full mb-3 flex items-center justify-center text-slate-400">
                    <span className="material-symbols-outlined text-2xl">inventory_2</span>
                  </div>
                  <div className="text-[14px] font-semibold text-slate-700 mb-1">暂无推荐资源</div>
                  <div className="text-[12px] text-slate-500 leading-relaxed px-2 mt-2">
                    完成检索能力验证后，这里会展示与本轮知识点相关的课程资源。
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Desktop Collapse Handle */}
          <button 
            onClick={() => setRightCollapsed(!rightCollapsed)}
            className="hidden xl:flex absolute left-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
            title={rightCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            <span className="material-symbols-outlined text-[16px] select-none">
              {rightCollapsed ? 'chevron_left' : 'chevron_right'}
            </span>
          </button>
        </aside>

      </div>
    </div>
  );
}
