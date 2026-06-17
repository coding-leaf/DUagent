export default function QuizProgressCard({ currentQuestionIndex, totalQuestions }) {
  const percent = Math.round(((currentQuestionIndex + 1) / (totalQuestions || 1)) * 100);
  
  return (
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
  );
}
