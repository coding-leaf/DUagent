import Icon from '../../Icon';

export default function QuizGenerationSection({
  quizGenTask,
  quizGenerating,
  quizGenTaskError,
  hasReadyKnowledge,
  hasActiveKnowledgeGraph,
  onStartQuizGeneration,
}) {
  return (
    <>
      <div className="my-6 border-t border-slate-200" />

      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900">生成保底题库</h3>
          <p className="mt-1 text-xs text-slate-500">按 KG 全部节点生成保底题库（每节点 3 单选 + 4 多选）。</p>
        </div>
        <button
          type="button"
          onClick={onStartQuizGeneration}
          disabled={quizGenerating || !hasReadyKnowledge || !hasActiveKnowledgeGraph}
          className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            quizGenerating || !hasReadyKnowledge || !hasActiveKnowledgeGraph
              ? 'cursor-not-allowed bg-slate-100 text-slate-400'
              : 'cursor-pointer bg-emerald-600 text-white hover:bg-emerald-700'
          }`}
        >
          <Icon name={quizGenerating ? 'progress_activity' : 'quiz'} className={`material-symbols-outlined text-[18px] ${quizGenerating ? 'animate-spin' : ''}`}/>
          {quizGenerating ? '生成中' : '生成题库'}
        </button>
      </div>

      {quizGenTaskError && (
        <div className="mt-2 break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          {quizGenTaskError}
        </div>
      )}

      {(quizGenTask?.status === 'processing'
        || quizGenTask?.status === 'completed'
        || quizGenTask?.status === 'partial'
        || quizGenTask?.status === 'failed') && (
        <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className={`inline-flex h-2 w-2 rounded-full ${
              quizGenTask.status === 'completed' ? 'bg-emerald-500' :
              quizGenTask.status === 'partial' ? 'bg-amber-500' :
              quizGenTask.status === 'failed' ? 'bg-red-500' : 'bg-amber-500 animate-pulse'
            }`}></span>
            <span className="text-xs text-slate-700 font-medium">
              题库生成 {quizGenTask.status === 'completed'
                ? '完成'
                : quizGenTask.status === 'partial'
                  ? '部分失败'
                  : quizGenTask.status === 'failed'
                    ? '失败'
                    : '进行中'}
              {(quizGenTask.status === 'completed' || quizGenTask.status === 'partial') && quizGenTask.result?.total_question_count
                ? `（${quizGenTask.result.completed_node_count}/${quizGenTask.result.total_node_count} 节点，共 ${quizGenTask.result.total_question_count} 题）`
                : ''}
            </span>
          </div>
          {(quizGenTask.status === 'failed' || quizGenTask.status === 'partial') && quizGenTask.error_message && (
            <div className="mt-2 text-xs text-red-600">{quizGenTask.error_message}</div>
          )}
        </div>
      )}
    </>
  );
}
