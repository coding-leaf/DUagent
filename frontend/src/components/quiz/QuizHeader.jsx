import Icon from '../Icon';

export default function QuizHeader({ 
  courseName, 
  currentKnowledgePoint,
  onExit 
}) {
  return (
    <header className="fixed top-0 z-50 w-full bg-white/80 backdrop-blur-md border-b border-slate-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
      <div className="relative flex items-center h-16 px-6 max-w-[1280px] mx-auto">
        <div className="flex items-center gap-4">
          <button 
            onClick={onExit} 
            className="p-2 hover:bg-slate-100 rounded-full transition-colors cursor-pointer flex items-center justify-center -ml-2 text-slate-600 hover:text-slate-900"
            title="返回上一页"
          >
            <Icon name="arrow_back" className="material-symbols-outlined"/>
          </button>
          <span className="text-xl font-bold tracking-tighter text-slate-900">{courseName}</span>
        </div>
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center gap-2">
          <Icon name="topic" className="material-symbols-outlined text-primary"/>
          <span className="font-body-md text-primary font-bold tracking-tight max-w-[240px] truncate">{currentKnowledgePoint || '练习'}</span>
        </div>
      </div>
    </header>
  );
}
