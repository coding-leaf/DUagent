import Icon from '../../Icon';
import { formatDateTime } from './formatters';
import TaskStatusPanel from './TaskStatusPanel';

export default function KnowledgeGraphSection({
  knowledgeGraphStatus,
  knowledgeGraphTask,
  knowledgeGraphTaskError,
  knowledgeGraphProcessing,
  knowledgeGraphGenerating,
  knowledgeGraphGenerationDisabled,
  onStartKnowledgeGraphGeneration,
}) {
  return (
    <section className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">知识图谱</h3>
          <p className="mt-1 text-xs text-slate-500">
            {knowledgeGraphStatus?.active_graph
              ? '当前显示的是该资源库的 active 知识图谱'
              : '当前资源库暂无 active 知识图谱'}
          </p>
        </div>
        <button
          data-testid="catalog-start-kg-generation"
          type="button"
          onClick={onStartKnowledgeGraphGeneration}
          disabled={knowledgeGraphGenerationDisabled}
          className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            knowledgeGraphGenerationDisabled
              ? 'cursor-not-allowed bg-slate-100 text-slate-400'
              : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
          }`}
        >
          <Icon name={knowledgeGraphProcessing ? 'progress_activity' : 'account_tree'} className={`material-symbols-outlined text-[18px] ${knowledgeGraphProcessing ? 'animate-spin' : ''}`}/>
          {knowledgeGraphProcessing || knowledgeGraphGenerating ? '刷新中' : '刷新图谱'}
        </button>
      </div>

      <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
        {knowledgeGraphStatus?.active_graph ? (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs font-bold text-slate-500">当前版本</div>
              <div className="mt-1 font-semibold text-slate-900">v{knowledgeGraphStatus.active_graph.version}</div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500">节点 / 边</div>
              <div className="mt-1 font-semibold text-slate-900">
                {knowledgeGraphStatus.active_graph.node_count ?? 0} / {knowledgeGraphStatus.active_graph.edge_count ?? 0}
              </div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500">来源</div>
              <div className="mt-1 font-semibold text-slate-900">{knowledgeGraphStatus.active_graph.source_type || '—'}</div>
            </div>
            <div>
              <div className="text-xs font-bold text-slate-500">创建时间</div>
              <div className="mt-1 font-semibold text-slate-900">{formatDateTime(knowledgeGraphStatus.active_graph.created_at)}</div>
            </div>
          </div>
        ) : (
          <div className="text-slate-500">暂无 active 知识图谱。</div>
        )}
      </div>

      <TaskStatusPanel
        data-testid="catalog-kg-task-status"
        task={knowledgeGraphTask}
        taskError={knowledgeGraphTaskError}
        fallbackText={
          knowledgeGraphStatus?.last_generation_task?.task_id
            ? `最近图谱任务 ${knowledgeGraphStatus.last_generation_task.task_id}`
            : '知识库就绪后可根据已入库切片刷新 active 图谱。'
        }
      />
    </section>
  );
}
