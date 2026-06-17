import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useCourse } from '../../context/CourseContext';
import { useChat } from '../../context/ChatContext';
import { learningService } from '../../api/services/learning';
import Icon from '../Icon';

export default function SidebarResources({ activeCourseName, rightCollapsed, rightDrawerOpen, onToggleCollapse, onCloseDrawer }) {
  const [resources, setResources] = useState([]);
  const { activeCourseId } = useCourse();
  const { messages } = useChat();

  useEffect(() => {
    if (activeCourseId) {
      learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 100 })
        .then(res => {
          if (res.code === 200 && res.data) {
            setResources(Array.isArray(res.data.resources || res.data) ? (res.data.resources || res.data) : []);
          }
        })
        .catch(console.error);
    } else {
      setResources([]);
    }
  }, [activeCourseId]);

  const activeKPs = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.knowledge_points && msg.knowledge_points.length > 0) {
        return msg.knowledge_points;
      }
    }
    return [];
  }, [messages]);

  const recommendedResources = useMemo(() => {
    return resources.filter(res => {
      if (activeKPs.length === 0) return true;
      return activeKPs.some(kp => 
        res.knowledge_point?.toLowerCase().includes(kp.toLowerCase()) ||
        res.title?.toLowerCase().includes(kp.toLowerCase())
      );
    });
  }, [resources, activeKPs]);

  return (
    <>
      {rightDrawerOpen && (
        <div 
          onClick={onCloseDrawer}
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 xl:hidden transition-opacity duration-300"
        />
      )}
      <aside className={`
        bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0 overflow-hidden
        /* Mobile Drawer Style */
        fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-full
        ${rightDrawerOpen ? 'translate-x-0' : 'translate-x-full xl:translate-x-0'}
        /* Desktop Collapse Style */
        ${rightCollapsed ? 'xl:w-16 xl:border-l xl:border-slate-200' : 'xl:w-72 xl:border-l xl:border-slate-200'}
      `}>
        <div className="w-72 h-full flex flex-col">
          <div className="flex-1 flex flex-col w-72 h-full">
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
                          <Icon name={icon} className="material-symbols-outlined text-[20px]"/>
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
                <div className="border border-slate-200 border-dashed rounded-xl p-4 bg-slate-50 flex flex-col items-center justify-center text-center mt-6">
                  <div className="w-12 h-12 bg-slate-100 rounded-full mb-3 flex items-center justify-center text-slate-400">
                    <Icon name="inventory_2" className="material-symbols-outlined text-2xl"/>
                  </div>
                  <div className="text-[14px] font-semibold text-slate-700 mb-1">暂无推荐资源</div>
                  <div className="text-[12px] text-slate-500 leading-relaxed px-2 mt-2">
                    这里会根据您的学习进度，为您推荐合适的课程资源。
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Desktop Collapse Handle */}
        <button 
          onClick={onToggleCollapse}
          className="hidden xl:flex absolute left-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
          title={rightCollapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          <Icon name={rightCollapsed ? 'chevron_left' : 'chevron_right'} className="material-symbols-outlined text-[16px] select-none"/>
        </button>
      </aside>
    </>
  );
}
