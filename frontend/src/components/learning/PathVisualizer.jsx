import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../Icon';

export default function PathVisualizer({ learningPath, loading, selectedNodeId, onSelectNode }) {
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        const speedMultiplier = 2.5; 
        container.scrollLeft += e.deltaY * speedMultiplier;
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, [loading]);

  return (
    <section className="bg-surface-container-lowest border border-gray-100 rounded-xl p-md shadow-sm overflow-hidden">
      <div className="flex items-center justify-between mb-lg">
        <h3 className="font-h3 text-h3 flex items-center space-x-sm">
          <Icon name="insights" className="material-symbols-outlined text-cyan-600"/>
          <span>闯关节点规划</span>
        </h3>
        <div className="flex space-x-base">
          <div className="flex items-center text-label-sm text-gray-400">
            <span className="w-3 h-3 rounded-full bg-cyan-500 mr-xs"></span> 已完成
          </div>
          <div className="flex items-center text-label-sm text-gray-400">
            <span className="w-3 h-3 rounded-full bg-surface-container-highest mr-xs"></span> 进行中
          </div>
        </div>
      </div>

      <div ref={scrollContainerRef} className="relative flex items-center py-xl overflow-x-auto no-scrollbar min-h-[300px]">
        {loading ? (
          <div className="w-full flex justify-center"><Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-cyan-500"/></div>
        ) : (
          <>
            <div className="absolute top-1/2 left-0 w-full h-[2px] bg-slate-200 -translate-y-1/2 z-0"></div>

            {learningPath?.nodes.map((node) => {
              if (node.status === 'completed') {
                return (
                  <div key={node.id}
                    onClick={() => onSelectNode(node.id)}
                    className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-emerald-500 ring-offset-2 rounded-xl' : ''}`}>
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3 border border-emerald-100 transition-colors group-hover:bg-emerald-100">
                      <Icon name="check" className="text-xl"/>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm w-full transition-all duration-200 group-hover:shadow-md">
                      <span className="text-[11px] font-semibold text-emerald-600 tracking-wider mb-1 block">阶段 {node.order}</span>
                      <p className="text-base font-medium text-slate-800 mb-4">{node.name}</p>
                      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 w-full"></div>
                      </div>
                    </div>
                  </div>
                );
              } else if (node.status === 'in_progress') {
                return (
                  <div key={node.id}
                    onClick={() => onSelectNode(node.id)}
                    className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-blue-500 ring-offset-2 rounded-xl' : ''}`}>
                    <div className="w-10 h-10 rounded-lg bg-blue-600 text-white flex items-center justify-center mb-3 shadow-md">
                      <Icon name="play_arrow" className="text-xl"/>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-blue-600 shadow-md w-full relative transition-all duration-200 group-hover:shadow-lg">
                      <div className="absolute -top-2.5 left-5 bg-blue-600 text-white text-[10px] font-bold tracking-wide px-2 py-0.5 rounded shadow-sm">进行中</div>
                      <span className="text-[11px] font-semibold text-blue-600 tracking-wider mb-1 block">阶段 {node.order}</span>
                      <p className="text-base font-medium text-slate-900 mb-4">{node.name}</p>
                      <div className="space-y-1.5">
                        <div className="flex justify-between text-[11px] font-medium text-slate-500">
                          <span>当前进度</span>
                          <span>{node.mastery}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-600 transition-all duration-500" style={{ width: `${node.mastery}%` }}></div>
                        </div>
                      </div>
                      <div className="mt-4">
                        <Link to="/dashboard" state={{ search: node.name }} className="w-full py-1.5 bg-slate-50 hover:bg-slate-100 text-blue-700 rounded-lg text-sm font-medium flex items-center justify-center gap-1.5 transition-colors border border-slate-200">
                          <Icon name="auto_stories" className="text-sm"/> 继续学习
                        </Link>
                      </div>
                    </div>
                  </div>
                );
              } else if (node.status === 'recommended') {
                return (
                  <div key={node.id}
                    onClick={() => onSelectNode(node.id)}
                    className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-indigo-400 ring-offset-2 rounded-xl' : ''}`}>
                    <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 border border-indigo-100 transition-colors group-hover:bg-indigo-100">
                      <Icon name="auto_awesome" className="text-xl"/>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-indigo-200 shadow-sm w-full transition-all duration-200 group-hover:shadow-md">
                      <span className="text-[11px] font-semibold text-indigo-600 tracking-wider mb-1 block">阶段 {node.order}</span>
                      <p className="text-base font-medium text-slate-800 mb-4">{node.name}</p>
                      <div className="h-1.5 w-full bg-indigo-50 rounded-full overflow-hidden mb-3">
                        <div className="h-full bg-indigo-300 w-0"></div>
                      </div>
                      <div className="text-[11px] font-medium text-indigo-500 flex items-center gap-1">
                        <Icon name="info" className="text-[14px]"/> 推荐预习
                      </div>
                    </div>
                  </div>
                );
              } else {
                return (
                  <div key={node.id}
                    onClick={() => onSelectNode(node.id)}
                    className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer opacity-80 hover:opacity-100 transition-opacity ${node.id === selectedNodeId ? 'ring-2 ring-slate-300 ring-offset-2 rounded-xl' : ''}`}>
                    <div className="w-10 h-10 rounded-lg bg-slate-100 text-slate-400 flex items-center justify-center mb-3 transition-colors group-hover:bg-slate-200 group-hover:text-slate-500">
                      <Icon name="explore" className="text-xl"/>
                    </div>
                    <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 w-full transition-all duration-200 group-hover:border-slate-300">
                      <span className="text-[11px] font-semibold text-slate-400 tracking-wider mb-1 block transition-colors group-hover:text-slate-500">阶段 {node.order}</span>
                      <p className="text-base font-medium text-slate-500 mb-4 transition-colors group-hover:text-slate-700">{node.name}</p>
                      <div className="h-1 w-full bg-slate-200 rounded-full"></div>
                      <div className="mt-3 text-[11px] font-medium text-slate-400 flex items-center gap-1 transition-colors group-hover:text-slate-500">
                        <Icon name="arrow_forward" className="text-[14px]"/> 尚未学习
                      </div>
                    </div>
                  </div>
                );
              }
            })}
          </>
        )}
      </div>
    </section>
  );
}
