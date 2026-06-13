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
  const { activeCourseId } = useCourse();
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

        // If it was a new conversation, fetch the new ID
        if (!activeSession && doneData.conversation_id) {
          setActiveSession(doneData.conversation_id);
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
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans pt-16">
      <Navbar />
      
      {/* Column 1: Left Sidebar (Context) */}
      <div className="w-64 bg-white border-r border-slate-200 flex flex-col flex-shrink-0 z-10 hidden md:flex">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <span className="font-semibold text-slate-700">当前课程</span>
          <span className="px-2 py-1 bg-cyan-50 text-cyan-700 text-xs rounded-md font-medium">进行中</span>
        </div>
        <div className="p-4">
          <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center mb-3">
            <span className="material-symbols-outlined text-[24px]">terminal</span>
          </div>
          <h3 className="font-bold text-slate-800 text-lg mb-1">C 语言程序设计</h3>
          <p className="text-slate-500 text-sm mb-4">掌握底层逻辑与内存管理的核心基础课程。</p>
          
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-600 p-2 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors">
              <span className="material-symbols-outlined text-[18px] text-slate-400">menu_book</span>
              <span>第 5 章：指针与数组</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600 p-2 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors">
              <span className="material-symbols-outlined text-[18px] text-slate-400">assignment</span>
              <span>实验作业：内存分配</span>
            </div>
          </div>
        </div>
      </div>

      {/* Column 2: Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full max-w-4xl mx-auto w-full shadow-2xl shadow-slate-200/50 bg-white">
        
        {/* Header */}
        <div className="h-14 border-b border-slate-100 flex items-center px-6 justify-between bg-white/80 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-sm font-medium text-slate-600">AI 助教已就绪</span>
          </div>
          <button className="text-slate-400 hover:text-slate-600 transition-colors cursor-pointer">
            <span className="material-symbols-outlined text-[20px]">more_horiz</span>
          </button>
        </div>

        {/* Messages / Empty State */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 scroll-smooth pb-32 custom-scrollbar">
          {messages.length === 0 ? (
            <ChatEmptyState onCardClick={handleSendMessage} />
          ) : (
            <div className="space-y-6">
              {messages.map(msg => (
                <ChatMessage 
                  key={msg.id} 
                  message={msg} 
                  onSendMessage={handleSendMessage} 
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-white via-white to-transparent pt-10">
          <div className="max-w-3xl mx-auto">
            <div className="relative flex items-end gap-2 bg-white border border-slate-200 rounded-2xl shadow-lg shadow-slate-200/50 p-2 focus-within:border-cyan-400 focus-within:ring-4 focus-within:ring-cyan-50 transition-all duration-300">
              <button className="p-2 text-slate-400 hover:text-cyan-600 transition-colors rounded-xl hover:bg-cyan-50 flex-shrink-0 cursor-pointer">
                <span className="material-symbols-outlined text-[22px]">attach_file</span>
              </button>
              
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="发送消息，或输入 '/' 获取快捷指令..."
                className="w-full max-h-32 min-h-[44px] bg-transparent border-none focus:ring-0 resize-none py-3 px-2 text-[15px] text-slate-700 placeholder:text-slate-400 leading-relaxed outline-none"
                rows={1}
              />
              
              <button
                onClick={() => handleSendMessage()}
                disabled={isSending || !inputValue.trim() || !activeCourseId}
                className={`p-3 rounded-xl flex items-center justify-center transition-all duration-300 flex-shrink-0 ${
                  inputValue.trim() && !isSending && activeCourseId
                    ? 'bg-cyan-600 text-white shadow-md hover:bg-cyan-700 hover:shadow-lg active:scale-95 cursor-pointer' 
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                }`}
              >
                {isSending ? (
                  <span className="material-symbols-outlined animate-spin text-[20px]">sync</span>
                ) : (
                  <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: '"FILL" 1' }}>send</span>
                )}
              </button>
            </div>
            <div className="text-center mt-3 text-xs text-slate-400">
              AI 可能会产生误导性信息，请结合课程资料核实。
            </div>
          </div>
        </div>
      </div>

      {/* Column 3: Right Sidebar (Recommendations) */}
      <div className="w-72 bg-slate-50 border-l border-slate-200 flex-col flex-shrink-0 z-10 hidden lg:flex">
        <div className="p-4 border-b border-slate-200/60 bg-slate-50/80 backdrop-blur-sm sticky top-0">
          <span className="font-semibold text-slate-700 flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-amber-500">auto_awesome</span>
            智能推荐
          </span>
        </div>
        <div className="p-4 overflow-y-auto custom-scrollbar">
          <div className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm mb-4 hover:shadow-md transition-shadow cursor-pointer group">
            <div className="flex items-center gap-2 mb-2 text-xs font-medium text-indigo-600 bg-indigo-50 w-fit px-2 py-1 rounded-md">
              <span className="material-symbols-outlined text-[14px]">play_circle</span>
              视频片段
            </div>
            <h4 className="font-medium text-slate-800 text-sm mb-1 group-hover:text-cyan-600 transition-colors">指针的内存模型详解</h4>
            <p className="text-xs text-slate-500 line-clamp-2">结合课程第 5 章的内容，这段 5 分钟的视频可以帮你快速回顾...</p>
          </div>
          
          <div className="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer group">
            <div className="flex items-center gap-2 mb-2 text-xs font-medium text-emerald-600 bg-emerald-50 w-fit px-2 py-1 rounded-md">
              <span className="material-symbols-outlined text-[14px]">quiz</span>
              随堂测试
            </div>
            <h4 className="font-medium text-slate-800 text-sm mb-1 group-hover:text-cyan-600 transition-colors">数组与指针易错题</h4>
            <p className="text-xs text-slate-500 line-clamp-2">检测你对刚才讨论的知识点的掌握程度，共 3 道选择题。</p>
          </div>
        </div>
      </div>
    </div>
  );
}
