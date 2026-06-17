import { useChat } from '../../context/ChatContext';
import Icon from '../Icon';

export default function SidebarHistory({ leftCollapsed, leftDrawerOpen, onToggleCollapse, onCloseDrawer, onNewChat }) {
  const { sessions, activeSession, setActiveSession, deleteSession } = useChat();

  return (
    <>
      {leftDrawerOpen && (
        <div 
          onClick={onCloseDrawer}
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden transition-opacity duration-300"
        />
      )}
      <aside className={`
        bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0 overflow-hidden
        /* Mobile Drawer Style */
        fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-full
        ${leftDrawerOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        /* Desktop Collapse Style */
        ${leftCollapsed ? 'lg:w-16 lg:border-r lg:border-slate-200' : 'lg:w-64 lg:opacity-100 lg:border-r lg:border-slate-200'}
      `}>
        <div className="w-64 h-full flex flex-col transition-opacity duration-300">
          <div className="flex-1 flex flex-col w-64 h-full">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-slate-800">
                <div className="w-6 h-6 bg-cyan-500 rounded text-white flex items-center justify-center text-[10px]">AI</div>
                智能学习助手
              </div>
              <button 
                onClick={onNewChat}
                className="text-cyan-600 hover:bg-cyan-50 p-1.5 rounded-lg transition-colors cursor-pointer"
                title="新对话"
              >
                <Icon name="add" className="material-symbols-outlined text-[18px]"/>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
              <div className="px-3 py-2 text-xs font-bold text-slate-400 mb-1">历史记录</div>
              {sessions.map(session => (
                <div key={session.id} className="group/session flex items-center">
                  <div
                    onClick={() => {
                      setActiveSession(session.id);
                      onCloseDrawer();
                    }}
                    className={`flex-1 px-3 py-2 rounded-lg cursor-pointer text-[13px] transition-colors flex items-center gap-2 ${
                      activeSession === session.id
                        ? 'bg-slate-100 text-slate-800 font-semibold'
                        : 'text-slate-500 hover:bg-slate-50'
                    }`}
                    title={session.title}
                  >
                    <Icon name="chat_bubble_outline" className="material-symbols-outlined text-[16px] flex-shrink-0"/>
                    <span className="truncate">{session.title}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!window.confirm('确定删除该对话？删除后不可恢复。')) return;
                      deleteSession(session.id);
                    }}
                    className="opacity-0 group-hover/session:opacity-100 px-2 py-1 text-slate-400 hover:text-red-500 cursor-pointer transition-all"
                    title="删除对话"
                  >
                    <Icon name="delete" className="material-symbols-outlined text-[16px]"/>
                  </button>
                </div>
              ))}
              {sessions.length === 0 && (
                <p className="text-xs text-slate-400 px-3 py-4">无历史对话</p>
              )}
            </div>
          </div>
        </div>

        {/* Desktop Collapse Handle */}
        <button 
          onClick={onToggleCollapse}
          className="hidden lg:flex absolute right-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
          title={leftCollapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          <Icon name={leftCollapsed ? 'chevron_right' : 'chevron_left'} className="material-symbols-outlined text-[16px] select-none"/>
        </button>
      </aside>
    </>
  );
}
