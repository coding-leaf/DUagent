import Icon from '../../Icon';
import TaskStatusPanel from './TaskStatusPanel';

export default function IngestionSection({
  knowledgeStatus,
  activeTask,
  taskError,
  taskProcessing,
  ingesting,
  startDisabled,
  onStartIngestion,
}) {
  return (
    <section data-testid="catalog-task-status" className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">入库任务</h3>
          <p className="mt-1 text-xs text-slate-500">
            {knowledgeStatus?.last_ingestion_task_id ? `最近任务 ${knowledgeStatus.last_ingestion_task_id}` : '暂无历史任务'}
          </p>
        </div>
        <button
          data-testid="catalog-start-ingestion"
          type="button"
          onClick={onStartIngestion}
          disabled={startDisabled}
          className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            startDisabled
              ? 'cursor-not-allowed bg-slate-100 text-slate-400'
              : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
          }`}
        >
          <Icon name={taskProcessing ? 'progress_activity' : 'play_arrow'} className={`material-symbols-outlined text-[18px] ${taskProcessing ? 'animate-spin' : ''}`}/>
          {taskProcessing || ingesting ? '入库中' : '开始入库'}
        </button>
      </div>

      <TaskStatusPanel
        data-testid="catalog-ingestion-task-status"
        task={activeTask}
        taskError={taskError}
        fallbackText={knowledgeStatus?.last_error || '点击开始入库后将在此显示任务状态。'}
      />
    </section>
  );
}
