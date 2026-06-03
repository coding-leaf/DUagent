import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { chatService } from '../api/services/chat';

export default function AIChat() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    chatService.getSessions().then(res => {
      if (res.code === 200) {
        setSessions(res.data);
        if (res.data.length > 0) setActiveSession(res.data[0].session_id);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (activeSession) {
      chatService.getHistory(activeSession).then(res => {
        if (res.code === 200) {
          setMessages(res.data.messages || []);
          setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
        }
      }).catch(console.error);
    }
  }, [activeSession]);

  const handleSendMessage = () => {
    if (!inputValue.trim() || isSending) return;
    const msgText = inputValue;
    setInputValue('');
    
    // Optimistic UI update
    const newMsg = { id: 'temp-' + Date.now(), role: 'user', content: msgText };
    setMessages(prev => [...prev, newMsg]);
    setIsSending(true);
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);

    chatService.sendMessage(activeSession, msgText).then(res => {
      if (res.code === 200) {
        setMessages(prev => [...prev, res.data]);
        setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
      }
    }).catch(console.error).finally(() => setIsSending(false));
  };
  return (
    <div className="font-body-md text-on-background bg-background min-h-screen">
      {/* TopNavBar */}
      <header className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-gray-100 shadow-sm font-['Public_Sans'] antialiased">
        <div className="flex items-center justify-between px-6 h-16 max-w-[1280px] mx-auto relative">
          <div className="flex items-center">
            <span className="text-xl font-bold tracking-tight text-cyan-600">数据结构智能助手</span>
          </div>
          <nav className="hidden md:flex items-center space-x-8 absolute left-1/2 -translate-x-1/2">
            <Link to="/profile" className="text-gray-600 hover:text-cyan-50 transition-colors">个人信息</Link>
            <Link to="/learning-path" className="text-gray-600 hover:text-cyan-50 transition-colors">路径规划</Link>
            <Link to="/dashboard" className="text-gray-600 hover:text-cyan-50 transition-colors">资源库</Link>
            <Link to="/ai-chat" className="text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1">AI答疑</Link>
            <Link to="/learning-effects" className="text-gray-600 hover:text-cyan-500 transition-colors">学习效果</Link>
          </nav>
          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-gray-50 rounded-lg transition-all active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-gray-600">notifications</span>
            </button>
            <button className="p-2 hover:bg-gray-50 rounded-lg transition-all active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-gray-600">settings</span>
            </button>
            <img 
              alt="用户头像" 
              className="w-8 h-8 rounded-full border border-gray-200 object-cover" 
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuDfQu5sK-V7EbXBUDlh6kjwwkNR5pdom0FK1_3cafAOLjQkJsGkpsUbNxPRq72U74LZF2hZ7O1v59Z-yIhiCRPQvCgeh7EynAmocFsNtBnxkOzW8K24s2lGRS5X944k7PL-2Nrwf3B3FVrqpFtH-Wp2mfH9mLesN1RMzA_sKknDKaSbys7LW3NCJG0WUMlJ0iSryXU6ZJ_SOYfuJWvuJsJ2cG4wesJ-Syz2Y1PSEeFljmyuX2tLfES_2cr8lfGIqst5YsZpzoiivFur" 
            />
          </div>
        </div>
      </header>

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
          <button onClick={() => navigate('/dashboard')} className="w-full mt-4 bg-primary-container text-on-primary-container py-2 rounded-lg font-semibold active:scale-95 transition-all cursor-pointer">
            启动新任务
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 space-y-1">
          <div className="px-2 py-1 text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">历史记录</div>
          {sessions.map(session => (
            <div 
              key={session.session_id} 
              onClick={() => setActiveSession(session.session_id)}
              className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer hover:pl-4 transition-all duration-200 ${activeSession === session.session_id ? 'bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500' : 'text-gray-500 hover:bg-gray-50'}`}
            >
              <span className="material-symbols-outlined">{session.icon || 'chat'}</span>
              <span>{session.title}</span>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Content Stage */}
      <main className="flex-1 ml-0 md:ml-64 relative pt-16">
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
              <button className="flex items-center gap-1 px-4 py-2 text-cyan-600 border border-cyan-200 rounded-lg hover:bg-cyan-50 transition-all text-label-sm cursor-pointer">
                <span className="material-symbols-outlined text-sm">refresh</span>
                重置对话
              </button>
            </div>
          </div>

          {/* Chat Scroll Area */}
          <div className="flex-1 overflow-y-auto space-y-6 pb-32 px-2 custom-scrollbar">
            
            {messages.map(msg => (
              <div key={msg.id} className={`flex gap-4 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center ${msg.role === 'user' ? 'bg-primary-container text-white' : 'bg-cyan-100 text-cyan-600'}`}>
                  <span className="material-symbols-outlined text-sm" style={msg.role !== 'user' ? { fontVariationSettings: '"FILL" 1' } : {}}>
                    {msg.role === 'user' ? 'person' : 'smart_toy'}
                  </span>
                </div>
                <div className={`p-4 rounded-2xl w-full ${msg.role === 'user' ? 'chat-bubble-user rounded-tr-none' : 'chat-bubble-ai rounded-tl-none'}`}>
                  <p className="text-body-md text-on-surface whitespace-pre-wrap">{msg.content}</p>
                  
                  {msg.suggestions && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {msg.suggestions.map((sug, i) => (
                        <span key={i} onClick={() => { setInputValue(sug); setTimeout(handleSendMessage, 0); }} className="px-3 py-1 bg-surface-container text-primary text-xs rounded-full cursor-pointer hover:bg-primary-fixed transition-colors">
                          {sug}
                        </span>
                      ))}
                    </div>
                  )}

                  {msg.has_visual && (
                    <div className="bg-gray-50 rounded-xl p-6 border border-dashed border-gray-200 mt-4 mb-4 relative overflow-hidden group">
                      <div className="flex justify-center items-center py-12">
                        <div className="relative w-full h-48">
                          {/* Simplified Tree Representation */}
                          <div className="absolute left-1/2 -translate-x-1/2 top-0 w-10 h-10 rounded-full border-2 border-cyan-500 bg-white flex items-center justify-center font-bold text-cyan-600 shadow-sm z-10">20</div>
                          <div className="absolute left-1/3 top-16 w-8 h-8 rounded-full border-2 border-gray-300 bg-white flex items-center justify-center text-sm text-gray-400">10</div>
                          <div className="absolute right-1/3 top-16 w-8 h-8 rounded-full border-2 border-cyan-400 bg-white flex items-center justify-center text-sm text-cyan-600 font-bold">30</div>
                          <svg className="absolute top-0 left-0 w-full h-full opacity-30" viewBox="0 0 100 100" preserveAspectRatio="none">
                            <line x1="50" y1="20" x2="35" y2="70" stroke="#94a3b8" strokeWidth="1.5"></line>
                            <line x1="50" y1="20" x2="65" y2="70" stroke="#00d1ff" strokeWidth="1.5"></line>
                          </svg>
                        </div>
                      </div>
                      <div className="absolute inset-0 bg-white/40 backdrop-blur-[1px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="bg-white px-4 py-2 rounded-lg shadow-lg border border-gray-100 flex items-center gap-2 text-cyan-600 font-bold text-sm cursor-pointer">
                          <span className="material-symbols-outlined text-sm">play_arrow</span>
                          播放模拟
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isSending && (
               <div className="flex gap-4 max-w-[85%]">
                 <div className="w-8 h-8 rounded-full bg-cyan-100 flex-shrink-0 flex items-center justify-center">
                   <span className="material-symbols-outlined text-cyan-600 text-sm" style={{ fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
                 </div>
                 <div className="chat-bubble-ai p-4 rounded-2xl rounded-tl-none w-16 flex justify-center items-center">
                   <span className="material-symbols-outlined animate-spin text-cyan-600">progress_activity</span>
                 </div>
               </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Anchor */}
          <div className="fixed bottom-gutter left-gutter lg:left-[280px] right-gutter max-w-[1280px] xl:mx-auto bg-background pb-gutter pt-4 px-6 md:px-8">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-2 flex items-end gap-2">
              <button className="p-3 text-gray-400 hover:text-cyan-500 transition-all cursor-pointer">
                <span className="material-symbols-outlined">attach_file</span>
              </button>
              <div className="flex-1 min-h-[48px] max-h-32 overflow-y-auto px-2 py-3">
                <textarea 
                  className="w-full border-none focus:ring-0 p-0 text-body-md placeholder-gray-400 resize-none outline-none" 
                  placeholder="在这里输入你的问题，或者输入 / 呼唤特定智能体..." 
                  rows="1"
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
                  onClick={handleSendMessage}
                  disabled={isSending || !inputValue.trim()}
                  className="bg-primary-container text-on-primary-container disabled:opacity-50 w-10 h-10 rounded-xl flex items-center justify-center shadow-md active:scale-90 transition-all cursor-pointer hover:bg-primary-container/90"
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

      {/* FAB for quick action (only on main screens) */}
      <button className="fixed bottom-24 right-8 w-14 h-14 bg-cyan-600 text-white rounded-full shadow-2xl flex items-center justify-center active:scale-90 transition-transform lg:hidden cursor-pointer">
        <span className="material-symbols-outlined">add</span>
      </button>

    </div>
  );
}
