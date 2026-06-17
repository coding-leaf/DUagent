
import Icon from '../Icon';

export default function QuizHeader({ 
  currentQuestionIndex, 
  totalQuestions, 
  courseName, 
  currentKnowledgePoint,
  onExit 
}) {
  const percent = Math.round(((currentQuestionIndex + 1) / totalQuestions) * 100);
  
  return (
    <>
      <header className="fixed top-0 z-50 w-full bg-white/80 backdrop-blur-md border-b border-slate-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
        <div className="relative flex justify-between items-center h-16 px-6 max-w-[1280px] mx-auto">
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
          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-slate-50 rounded-full transition-colors active:scale-95 duration-200 cursor-pointer">
              <Icon name="analytics" className="material-symbols-outlined text-slate-600"/>
            </button>
            <button className="p-2 hover:bg-slate-50 rounded-full transition-colors active:scale-95 duration-200 cursor-pointer">
              <Icon name="notifications" className="material-symbols-outlined text-slate-600"/>
            </button>
            <div className="w-8 h-8 rounded-full overflow-hidden border border-slate-200">
              <img alt="用户头像" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBD7zzVzJP4sOCCImNhQnVh0f5VXBKYUUdqITWBaQkw7NykTFWpBCRb35x5OdjOfAeHA8pxnY1dbeHj7om4AmK_nGXsoIN-1mbwE3hCNq7xFNt4SuldmZvdW3PqPIvYRwW_EBGaXqZId-3waaJh8IQcMRBeypeQMRJI5hJFBhbeybYWhNhoWkUKSfTBuQqCIzu6dKwDMXS9LUFS_FZN0utek2XOAcc_3gZ3uXN6djZJ4T2_TfvwsvZ-1jgokz1Htpu6VTO_yqFDEOvS" />
            </div>
          </div>
        </div>
      </header>

      <div className="bg-white rounded-2xl p-6 mb-8 border border-slate-200 shadow-[0px_4px_20px_rgba(0,0,0,0.04)]">
        <div className="flex justify-between items-end mb-4">
          <div>
            <span className="text-primary font-bold text-h3 font-h3">{currentQuestionIndex + 1}</span>
            <span className="text-slate-400 font-body-md"> / {totalQuestions} 题</span>
          </div>
          <div className="text-right">
            <span className="text-slate-500 font-label-sm text-[11px] block mb-1">完成进度 {percent}%</span>
          </div>
        </div>
        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${percent}%` }}></div>
        </div>
      </div>
    </>
  );
}
