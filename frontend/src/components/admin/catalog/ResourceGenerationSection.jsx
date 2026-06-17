import Icon from '../../Icon';
import { RESOURCE_TYPE_OPTIONS } from './formatters';
import TaskStatusPanel from './TaskStatusPanel';

export default function ResourceGenerationSection({
  generationForm,
  generationTask,
  generationTaskError,
  generationProcessing,
  generating,
  generationDisabled,
  hasReadyKnowledge,
  hasActiveKnowledgeGraph,
  hasExplicitResourceTarget,
  onStartGeneration,
  onFieldChange,
  onTypeToggle,
}) {
  return (
    <section className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">生成学习资源</h3>
          <p className="mt-1 text-xs text-slate-500">基于已入库知识生成资源库共享资源；绑定该资源库的教学班都会读取到这批资源。</p>
        </div>
        <button
          type="button"
          onClick={onStartGeneration}
          disabled={generationDisabled}
          className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            generationDisabled
              ? 'cursor-not-allowed bg-slate-100 text-slate-400'
              : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
          }`}
        >
          <Icon name={generationProcessing ? 'progress_activity' : 'auto_awesome'} className={`material-symbols-outlined text-[18px] ${generationProcessing ? 'animate-spin' : ''}`}/>
          {generationProcessing || generating ? '生成中' : '生成资源'}
        </button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <input
          type="text"
          placeholder="章节"
          value={generationForm.chapter}
          onChange={(event) => onFieldChange('chapter', event.target.value)}
          disabled={generationProcessing || generating}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none transition-colors focus:border-cyan-500 disabled:bg-slate-50 disabled:text-slate-400"
        />
        <input
          type="text"
          placeholder="知识点"
          value={generationForm.knowledge_point}
          onChange={(event) => onFieldChange('knowledge_point', event.target.value)}
          disabled={generationProcessing || generating}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none transition-colors focus:border-cyan-500 disabled:bg-slate-50 disabled:text-slate-400"
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {RESOURCE_TYPE_OPTIONS.map((option) => (
          <label
            key={option.value}
            className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
              generationForm.resource_types.includes(option.value)
                ? 'border-cyan-300 bg-cyan-50 text-cyan-700'
                : 'border-slate-200 bg-white text-slate-600'
            } ${generationProcessing || generating ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-cyan-200'}`}
          >
            <input
              type="checkbox"
              checked={generationForm.resource_types.includes(option.value)}
              disabled={generationProcessing || generating}
              onChange={() => onTypeToggle(option.value)}
              className="h-4 w-4 accent-cyan-600"
            />
            {option.label}
          </label>
        ))}
      </div>

      {!hasReadyKnowledge && (
        <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
          知识库就绪且存在知识切片后才能生成学习资源。
        </div>
      )}
      {hasReadyKnowledge && hasActiveKnowledgeGraph && !hasExplicitResourceTarget && (
        <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
          将按 KG 节点自动生成并挂载资源。
        </div>
      )}
      {hasReadyKnowledge && !hasActiveKnowledgeGraph && !hasExplicitResourceTarget && (
        <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
          先刷新 active 知识图谱后，才能按 KG 节点自动生成资源。
        </div>
      )}

      <TaskStatusPanel
        data-testid="catalog-generation-task-status"
        task={generationTask}
        taskError={generationTaskError}
        fallbackText="选择资源类型后可触发生成任务。"
      />
    </section>
  );
}
