import { useState, useRef, useEffect } from 'react';
import Icon from '../Icon';

const pluginMeta = {
  QuizCard: { title: '随堂测试', icon: 'quiz' },
  Mermaid: { title: '流程拓扑图', icon: 'account_tree' },
  Markdown: { title: '讲解备忘录', icon: 'description' },
  StudyPlanCard: { title: '今日学习计划', icon: 'calendar_today' },
  WeakPointsCard: { title: '薄弱知识点', icon: 'insights' },
  PathRecommendationCard: { title: '学习路径推荐', icon: 'route' },
  CodeSandboxCard: { title: '代码实操练习', icon: 'code' }
};

export default function WorkspaceTabs({
  artifacts,
  activeId,
  onSelect,
  onClose,
  hiddenArtifacts = [],
  onRestore
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if ((!artifacts || artifacts.length === 0) && hiddenArtifacts.length === 0) return null;

  const getArtifactTitle = (art) => {
    return art.props?.title || art.title || pluginMeta[art.type]?.title || art.type;
  };

  const getArtifactIcon = (art) => {
    return art.props?.icon || art.icon || pluginMeta[art.type]?.icon || 'insert_drive_file';
  };

  return (
    <div className="flex items-center justify-between border-b border-slate-200 p-1 bg-slate-50/50 rounded-t-lg select-none">
      {/* Visible Tabs list */}
      <div className="flex gap-1 overflow-x-auto custom-scrollbar flex-1 pr-4">
        {artifacts.map(art => {
          const isActive = activeId === art.id;
          return (
            <div
              key={art.id}
              onClick={() => onSelect(art.id)}
              className={`group relative flex items-center gap-2 px-3 py-1.5 rounded-t-md text-xs font-medium transition-all duration-200 cursor-pointer border-t-2 ${
                isActive
                  ? 'bg-white text-cyan-600 border-cyan-500 shadow-sm'
                  : 'bg-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-700 border-transparent'
              }`}
            >
              <Icon name={getArtifactIcon(art)} className="text-sm shrink-0" />
              <span className="truncate max-w-[120px]">{getArtifactTitle(art)}</span>
              
              {onClose && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onClose(art.id);
                  }}
                  className="flex items-center justify-center w-4 h-4 rounded-full text-slate-400 hover:text-red-500 hover:bg-slate-100 transition-colors ml-1"
                  title="关闭卡片"
                >
                  <Icon name="close" className="text-[10px]" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Recover / Restore Dropdown */}
      {hiddenArtifacts.length > 0 && onRestore && (
        <div className="relative shrink-0" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-md text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-800 transition-colors shadow-sm"
          >
            <Icon name="add" className="text-sm" />
            <span>找回已关闭 ({hiddenArtifacts.length})</span>
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-1.5 w-52 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-50 animate-fadeIn min-w-[200px]">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-400 border-b border-slate-100">
                已收起卡片列表
              </div>
              <div className="max-h-48 overflow-y-auto custom-scrollbar">
                {hiddenArtifacts.map(art => (
                  <button
                    key={art.id}
                    onClick={() => {
                      onRestore(art.id);
                      setDropdownOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors flex items-center gap-2"
                  >
                    <Icon name={getArtifactIcon(art)} className="text-sm text-slate-400" />
                    <span className="truncate flex-1">{getArtifactTitle(art)}</span>
                    <span className="text-[10px] text-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity">还原</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
