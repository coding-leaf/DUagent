import { useState, useEffect, useRef } from 'react';
import { useChat } from '../../context/ChatContext';
import { useCourse } from '../../context/CourseContext';
import ChatMessage from './ChatMessage';
import ChatEmptyState from './ChatEmptyState';
import Icon from '../Icon';

const QUICK_ACTIONS = [
  { key: 'weak_plan', label: '补弱计划', icon: 'route', prompt: '帮我根据当前薄弱点生成补弱学习计划。' },
  { key: 'resources', label: '推荐资源', icon: 'library_books', prompt: '请根据我的薄弱点推荐一组资源。' },
  { key: 'lesson', label: '讲解页', icon: 'auto_stories', prompt: '生成一个二叉树遍历的讲解页。' },
  { key: 'quiz', label: '练习预览', icon: 'quiz', prompt: '生成一道二叉树遍历练习预览。' },
];

export default function ChatArea({ activeCourseName, onOpenLeftDrawer }) {
  const { 
    sessions, activeSession, messages, isSending,
    sendMessage, editMessage, cancelStream, regenerate
  } = useChat();
  const { activeCourseId } = useCourse();
  
  const [inputValue, setInputValue] = useState('');
  const [editingMsg, setEditingMsg] = useState(null);
  const [planMode, setPlanMode] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const frameId = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    });
    return () => cancelAnimationFrame(frameId);
  }, [messages]);



  const handleSendMessage = (overrideText = '') => {
    const textToSend = (overrideText || inputValue).trim();
    if (!textToSend || isSending || !activeCourseId) return;
    if (!overrideText) setInputValue('');
    if (planMode) {
      sendMessage(textToSend, { planMode: true });
    } else {
      sendMessage(textToSend);
    }
  };

  const handleEditSubmit = (newContent) => {
    editMessage(newContent);
    setEditingMsg(null);
  };

  const handleTextareaChange = (e) => {
    setInputValue(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 128) + 'px';
  };

  return (
    <main className="w-full h-full flex flex-col relative bg-white border-l border-slate-200 overflow-hidden">
      
      {/* Top Context Bar */}
      <div className="h-14 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between px-5 lg:px-7 z-10 flex-shrink-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <button 
            onClick={onOpenLeftDrawer}
            className="lg:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer mr-1 flex items-center justify-center"
            title="打开历史记录"
          >
            <Icon name="menu" className="material-symbols-outlined text-[20px]"/>
          </button>
          
          <div className="text-sm text-slate-700 font-medium truncate">
            {activeSession ? sessions.find(s => s.id === activeSession)?.title || '对话中' : '新对话'}
          </div>
        </div>
        <div className="text-[11px] text-slate-400 truncate max-w-[160px]" title={activeCourseName}>
          {activeCourseName}
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4 lg:px-7 py-7">
        <div className="max-w-[820px] mx-auto space-y-9 pb-5">
          
          {messages.length === 0 ? (
            <ChatEmptyState onCardClick={handleSendMessage} courseName={activeCourseName} />
          ) : (
            (() => {
              const lastUserIndex = messages.map(m => m.role).lastIndexOf('user');
              const lastAiIndex = messages.map(m => m.role).lastIndexOf('assistant');
              return messages.map((msg, idx) => {
                const isLastUser = idx === lastUserIndex;
                const isLastAi = idx === lastAiIndex;
                return (
                  <div key={msg.id} className="group/message relative pb-3">
                    <ChatMessage
                      message={msg}
                      onSendMessage={handleSendMessage}
                      onRegenerate={regenerate}
                      isLastAssistant={isLastAi}
                    />

                  {isLastUser && editingMsg && editingMsg.msgId === msg.id ? (
                    <div className="mt-2 bg-white border border-cyan-300 rounded-lg p-3 shadow-sm">
                      <textarea
                        className="w-full border-none focus:ring-0 px-2 py-1 text-[15px] text-slate-800 resize-none outline-none rounded-lg bg-slate-50 min-h-[60px]"
                        value={editingMsg.content}
                        onChange={e => setEditingMsg({ ...editingMsg, content: e.target.value })}
                        autoFocus
                      />
                      <div className="flex justify-end gap-2 mt-2">
                        <button
                          onClick={() => setEditingMsg(null)}
                          className="px-3 py-1.5 text-[13px] rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer transition-colors"
                        >
                          取消
                        </button>
                        <button
                          onClick={() => {
                            handleEditSubmit(editingMsg.content);
                            setEditingMsg(null);
                          }}
                          disabled={!editingMsg.content.trim() || isSending}
                          className="px-3 py-1.5 text-[13px] rounded-lg bg-cyan-500 text-white hover:bg-cyan-600 cursor-pointer disabled:opacity-50 transition-colors"
                        >
                          发送修改
                        </button>
                      </div>
                    </div>
                  ) : null}

                  <div className="absolute -bottom-1 right-2 flex gap-0.5 opacity-0 group-hover/message:opacity-100 transition-opacity">
                    {isLastUser && !editingMsg && !isSending && (
                      <button
                        onClick={() => setEditingMsg({ msgId: msg.id, content: typeof msg.content === 'string' ? msg.content : '' })}
                        className="w-7 h-7 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 cursor-pointer transition-all text-[14px]"
                        title="编辑"
                      >
                        <Icon name="edit" className="material-symbols-outlined text-[16px]"/>
                      </button>
                    )}
                  </div>
                </div>
              );
              });
            })()
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Composer */}
      <div className="p-4 lg:px-6 pb-6 bg-gradient-to-t from-white/90 via-white/80 to-transparent flex-shrink-0">
        <div className="max-w-[820px] mx-auto">
          <div className="mb-3 flex flex-wrap gap-2 px-1">
            <button
              type="button"
              onClick={() => setPlanMode(value => !value)}
              disabled={!activeCourseId || isSending}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-[11px] font-semibold shadow-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                planMode
                  ? 'border-cyan-300 bg-cyan-50 text-cyan-700'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700'
              }`}
              aria-pressed={planMode}
            >
              <Icon name="list_alt" className="text-[14px]" />
              计划模式
            </button>
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.key}
                type="button"
                onClick={() => handleSendMessage(action.prompt)}
                disabled={!activeCourseId || isSending}
                className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 shadow-sm transition-colors hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Icon name={action.icon} className="text-[14px]" />
                {action.label}
              </button>
            ))}
          </div>
          
          <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-2.5 flex items-end gap-2 focus-within:border-cyan-400 focus-within:ring-4 focus-within:ring-cyan-500/10 transition-all">
            <textarea 
              className="flex-1 border-none focus:ring-0 px-2 py-2 text-[14px] text-slate-800 placeholder-slate-400 resize-none outline-none max-h-32 bg-transparent" 
              placeholder="在这里输入你的问题..." 
              rows={1}
              value={inputValue}
              onChange={handleTextareaChange}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
            ></textarea>
            
            <div className="flex justify-end items-center px-1 pb-1">
              {isSending ? (
                <button
                  onClick={() => cancelStream()}
                  className="w-8 h-8 rounded-lg bg-red-500 text-white flex items-center justify-center cursor-pointer hover:bg-red-600 active:scale-95 transition-all shadow-sm"
                  title="停止生成"
                >
                  <Icon name="close" className="material-symbols-outlined text-[16px]"/>
                </button>
              ) : (
                <button
                  data-testid="send-message-button"
                  onClick={() => handleSendMessage()}
                  disabled={!inputValue.trim() || !activeCourseId}
                  className="w-8 h-8 rounded-lg bg-cyan-500 text-white flex items-center justify-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-600 active:scale-95 transition-all shadow-sm"
                >
                  <Icon name="arrow_upward" className="material-symbols-outlined text-[16px]"/>
                </button>
              )}
            </div>
          </div>
          <div className="text-center mt-2 text-[11px] text-slate-400">
            AI 生成内容仅供学习参考
          </div>
        </div>
      </div>
    </main>
  );
}
