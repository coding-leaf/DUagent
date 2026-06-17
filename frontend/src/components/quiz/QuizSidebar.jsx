
import Icon from '../Icon';

export default function QuizSidebar({ 
  currentChapter,
  sourceLabel,
  difficulty,
  knowledgePoint, 
  questionTypeLabel
}) {
  const metadataItems = [
    { icon: 'topic', label: '知识点', value: knowledgePoint },
    { icon: 'speed', label: '难度', value: difficulty },
    { icon: 'quiz', label: '题型', value: questionTypeLabel }
  ];

  return (
    <aside className="h-screen w-64 border-r fixed left-0 top-0 bg-slate-50 border-slate-200 z-40 hidden xl:flex flex-col pt-20 pb-6 px-4 gap-2">
      <div className="px-4 py-4 mb-4">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white">
            <Icon name="smart_toy" className="material-symbols-outlined"/>
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">{currentChapter}</h3>
            <p className="text-xs text-slate-500 mt-1">{sourceLabel}</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 space-y-1">
        {metadataItems.map((item, index) => (
          <div
            key={item.label}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg ${
              index === 0
                ? 'bg-white text-primary shadow-sm border-l-4 border-primary font-bold'
                : 'text-slate-500 bg-slate-50'
            }`}
          >
            <Icon name={item.icon} className="material-symbols-outlined text-sm"/>
            <div className="min-w-0">
              <span className="font-label-sm text-[11px] text-slate-400 block">{item.label}</span>
              <span className="font-label-sm text-xs font-medium truncate block max-w-[150px]">{item.value}</span>
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
