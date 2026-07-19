import Icon from '../../Icon';
import { formatResourceType, formatDateTime } from './formatters';

export default function GeneratedResourceList({ resources, loading, resourceDeleteDisabled, deletingResourceIds, onDeleteResource }) {
  return (
    <section className="mb-5 rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-bold text-slate-900">生成资源列表</h3>
        {loading && <span className="text-xs text-slate-400">加载中...</span>}
      </div>
      <div className="max-h-80 overflow-y-auto">
        {resources.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">暂无生成资源</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {resources.map((resource) => (
              <div key={resource.id || resource.title} data-testid="catalog-resource-row" className="px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="break-words text-sm font-semibold text-slate-900">{resource.title || '未命名资源'}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>{formatResourceType(resource.type)}</span>
                      {resource.chapter && <span>章节 {resource.chapter}</span>}
                      {resource.knowledge_point && <span>知识点 {resource.knowledge_point}</span>}
                      <span>浏览 {resource.view_count ?? 0}</span>
                      <span>创建 {formatDateTime(resource.created_at)}</span>
                    </div>
                    {resource.description && (
                      <div className="mt-2 break-words text-xs text-slate-500">
                        {resource.description}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    aria-label="删除资源"
                    title="删除资源"
                    disabled={resourceDeleteDisabled || deletingResourceIds.has(resource.id) || !resource.id}
                    onClick={() => onDeleteResource(resource)}
                    className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg transition-colors ${
                      resourceDeleteDisabled || deletingResourceIds.has(resource.id) || !resource.id
                        ? 'cursor-not-allowed text-slate-300'
                        : 'text-red-500 hover:bg-red-50 hover:text-red-700'
                    }`}
                  >
                    <Icon name={deletingResourceIds.has(resource.id) ? 'progress_activity' : 'delete'} className="material-symbols-outlined text-[18px]"/>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
