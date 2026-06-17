import Icon from '../Icon';

export default function QuestionReviewList({ perQuestionResults }) {
  return (
    <div className="space-y-sm">
      <h4 className="font-label-sm text-label-sm text-secondary uppercase mb-base">详细解析回顾</h4>
      {perQuestionResults?.map((q, idx) => (
        <div key={q.question_id} className={`group flex items-center gap-md p-md bg-white border rounded-xl transition-all cursor-pointer ${q.is_correct ? 'border-outline-variant hover:border-primary-container' : 'border-error/20 hover:border-error'}`}>
          <div className={`flex-shrink-0 h-10 w-10 rounded-full flex items-center justify-center font-bold ${q.is_correct ? 'bg-green-50 text-green-600' : 'bg-error-container text-error'}`}>
            {idx + 1}
          </div>
          <div className="flex-1 min-w-0">
            <h5 className="font-body-md font-medium text-on-surface truncate">题号：{q.question_id} 的解析回顾</h5>
            <div className="flex gap-sm mt-1">
              <span className="font-label-sm text-[11px] text-secondary flex items-center gap-1">
                <Icon name={q.is_correct ? 'bolt' : 'timer'} className="material-symbols-outlined text-[14px]"/> 
                正确答案是 {q.correct_answer}
              </span>
              <span className={`font-label-sm text-[11px] font-bold ${q.is_correct ? 'text-green-600' : 'text-error'}`}>
                {q.is_correct ? '正确' : '错误'}
              </span>
            </div>
          </div>
          <Icon name="chevron_right" className="material-symbols-outlined text-secondary opacity-0 group-hover:opacity-100 transition-opacity"/>
        </div>
      ))}
      {(!perQuestionResults || perQuestionResults.length === 0) && (
        <div className="text-center py-4 text-slate-400">暂无详细解析</div>
      )}
    </div>
  );
}
