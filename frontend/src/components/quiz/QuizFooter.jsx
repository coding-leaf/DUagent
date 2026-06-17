import Icon from '../Icon';

export default function QuizFooter({ 
  isFirst, 
  isLast, 
  onPrevious, 
  onNextOrSubmit, 
  submitting,
  hasAnsweredCurrent
}) {
  return (
    <div className="fixed bottom-0 left-0 xl:left-64 right-0 bg-white/90 backdrop-blur-lg border-t border-slate-100 p-4 z-40">
      <div className="max-w-[800px] mx-auto flex justify-between items-center gap-4">
        <button 
          onClick={onPrevious}
          className="flex items-center gap-2 px-6 py-3 text-slate-600 font-bold hover:bg-slate-100 rounded-xl transition-all cursor-pointer"
        >
          <Icon name="arrow_back" className="material-symbols-outlined"/>
          {isFirst ? '退出练习' : '上一题'}
        </button>
        <div className="flex gap-4">
          <button 
            onClick={onNextOrSubmit}
            disabled={submitting || (!isLast && !hasAnsweredCurrent)}
            className="flex items-center gap-2 px-8 py-3 bg-primary text-white font-bold hover:opacity-90 rounded-xl transition-all shadow-lg shadow-primary/20 active:scale-95 cursor-pointer disabled:opacity-50"
          >
            {submitting ? '提交中...' : (isLast ? '提交本题' : '下一题')}
            {!submitting && <Icon name="chevron_right" className="material-symbols-outlined"/>}
          </button>
        </div>
      </div>
    </div>
  );
}
