import { useState, useEffect, useRef } from 'react';
import { useChat } from '../../context/ChatContext';
import { useCourse } from '../../context/CourseContext';
import ChatMessage from './ChatMessage';
import ChatEmptyState from './ChatEmptyState';
import Icon from '../Icon';

export default function ChatArea({ activeCourseName, onOpenLeftDrawer }) {
  const { 
    sessions, activeSession, messages, isSending,
    sendMessage, editMessage, cancelStream, regenerate,
    sendMockArtifact
  } = useChat();
  const { activeCourseId } = useCourse();
  
  const [inputValue, setInputValue] = useState('');
  const [editingMsg, setEditingMsg] = useState(null);
  const [showMockMenu, setShowMockMenu] = useState(false);
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
    sendMessage(textToSend);
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
    <main className="w-full lg:w-[380px] flex flex-col relative bg-slate-50 border-l border-slate-200 flex-shrink-0">
      
      {/* Top Context Bar */}
      <div className="h-14 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 z-10 flex-shrink-0">
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
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4 lg:px-8 py-8">
        <div className="max-w-[760px] mx-auto space-y-8 pb-4">
          
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
                    <ChatMessage message={msg} onSendMessage={handleSendMessage} />

                  {isLastUser && editingMsg && editingMsg.msgId === msg.id ? (
                    <div className="mt-2 bg-white border border-cyan-300 rounded-2xl p-3 shadow-sm">
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
                    {msg.role !== 'user' && !msg.loading && (
                      <button
                        onClick={() => navigator.clipboard?.writeText(typeof msg.content === 'string' ? msg.content : '').catch(console.error)}
                        className="w-7 h-7 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 cursor-pointer transition-all text-[14px]"
                        title="复制"
                      >
                        <Icon name="content_copy" className="material-symbols-outlined text-[16px]"/>
                      </button>
                    )}
                    {isLastAi && !msg.loading && !isSending && (
                      <button
                        onClick={regenerate}
                        className="w-7 h-7 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 cursor-pointer transition-all text-[14px]"
                        title="重新生成"
                      >
                        <Icon name="refresh" className="material-symbols-outlined text-[16px]"/>
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
      <div className="p-4 lg:px-8 pb-6 bg-gradient-to-t from-slate-50 via-slate-50 to-transparent flex-shrink-0">
        <div className="max-w-[760px] mx-auto">
          <div className="bg-white border border-slate-300 rounded-2xl shadow-sm p-3 flex flex-col gap-2 focus-within:border-cyan-400 focus-within:ring-2 focus-within:ring-cyan-100 transition-all relative">
            
            {showMockMenu && (
              <div className="absolute bottom-16 left-3 bg-white border border-slate-200 rounded-xl shadow-lg p-3 grid grid-cols-2 gap-2 z-50 animate-fadeIn text-xs w-64">
                <div className="col-span-2 font-bold text-slate-500 mb-1 border-b pb-1">触发模拟 Artifact</div>
                <button 
                  onClick={() => { 
                    sendMockArtifact({ 
                      type: 'QuizCard', 
                      props: { 
                        question: '以下哪个是线性数据结构？', 
                        choices: ['二叉树', '图', '队列', '网'], 
                        correctAnswer: 2 
                      } 
                    }); 
                    setShowMockMenu(false); 
                  }} 
                  className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer"
                >
                  + 测验卡片
                </button>
                <button 
                  onClick={() => { 
                    sendMockArtifact({ 
                      type: 'Mermaid', 
                      props: { 
                        chart: 'graph TD\nA[二叉树] --> B(二叉搜索树)\nA --> C(平衡二叉树)\nC --> D(AVL 树)' 
                      } 
                    }); 
                    setShowMockMenu(false); 
                  }} 
                  className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer"
                >
                  + 流程图
                </button>
                <button 
                  onClick={() => { 
                    sendMockArtifact({ 
                      type: 'Markdown', 
                      props: { 
                        content: '# 二叉树遍历详解\n\n1. **前序遍历** (根 -> 左 -> 右)\n2. **中序遍历** (左 -> 根 -> 右)\n3. **后序遍历** (左 -> 右 -> 根)' 
                      } 
                    }); 
                    setShowMockMenu(false); 
                  }} 
                  className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer"
                >
                  + Markdown 课件
                </button>
                <button 
                  onClick={() => { 
                    sendMockArtifact({ 
                      type: 'StudyPlanCard', 
                      props: { 
                        planDate: '2026-06-26', 
                        tasks: [
                          { name: '二叉树遍历 (重点突破)', duration: 60 }, 
                          { name: '递归思想强化训练', duration: 45 }, 
                          { name: '树的层序遍历与应用', duration: 45 }, 
                          { name: '今日小结与错题回顾', duration: 20 }
                        ] 
                      } 
                    }); 
                    setShowMockMenu(false); 
                  }} 
                  className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer"
                >
                  + 学习计划
                </button>
                <button 
                  onClick={() => { 
                    sendMockArtifact({ 
                      type: 'WeakPointsCard', 
                      props: { 
                        title: '薄弱点分析', 
                        points: [
                          { name: '二叉树遍历', mastery: 28 }, 
                          { name: '递归实现', mastery: 46 }, 
                          { name: '平衡二叉树 (AVL)', mastery: 58 }, 
                          { name: '图的最短路径', mastery: 72 }, 
                          { name: '哈希冲突处理', mastery: 80 }
                        ] 
                      } 
                    }); 
                    setShowMockMenu(false); 
                  }} 
                  className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer"
                >
                  + 薄弱点分析
                </button>
                <button 
                  onClick={() => { 
                    sendMockArtifact({ 
                      type: 'PathRecommendationCard', 
                      props: { 
                        strategy: '补强优先', 
                        duration: '18 天', 
                        target: '掌握树、图、哈希表等核心结构', 
                        steps: [
                          { name: '基础回顾' }, 
                          { name: '弱点突破' }, 
                          { name: '综合提升' }, 
                          { name: '专题拓展' }, 
                          { name: '项目实战' }
                        ] 
                      } 
                    }); 
                    setShowMockMenu(false); 
                  }} 
                  className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer"
                >
                  + 推荐路径
                </button>
              </div>
            )}

            <textarea 
              className="w-full border-none focus:ring-0 px-2 py-1 text-[15px] text-slate-800 placeholder-slate-400 resize-none outline-none max-h-32" 
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
            
            <div className="flex justify-between items-center px-1">
              <div className="flex gap-1 text-slate-400">
                <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-lg transition-colors cursor-pointer flex items-center justify-center">
                  <Icon name="attach_file" className="material-symbols-outlined text-[18px]"/>
                </button>
                <button className="p-1.5 hover:bg-slate-100 hover:text-slate-600 rounded-lg transition-colors cursor-pointer flex items-center justify-center">
                  <Icon name="mic" className="material-symbols-outlined text-[18px]"/>
                </button>
                <button 
                  onClick={() => setShowMockMenu(!showMockMenu)}
                  className={`p-1.5 rounded-lg transition-colors cursor-pointer flex items-center justify-center ${showMockMenu ? 'bg-cyan-50 text-cyan-600' : 'hover:bg-slate-100 hover:text-slate-600'}`}
                  title="生成模拟 Artifact"
                  data-testid="mock-artifact-button"
                >
                  <Icon name="data_object" className="material-symbols-outlined text-[18px]"/>
                </button>
              </div>
              
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
