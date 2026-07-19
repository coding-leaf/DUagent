import Icon from '../../Icon';
import { getBadgeClass, formatMaterialStatus, formatFileSize, formatDateTime } from './formatters';

export default function MaterialList({ materials, loading, materialDeleteDisabled, deletingMaterialIds, onDeleteMaterial }) {
  return (
    <section className="mb-5 rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-bold text-slate-900">资料列表</h3>
        {loading && <span className="text-xs text-slate-400">加载中...</span>}
      </div>
      <div className="max-h-72 overflow-y-auto">
        {materials.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">暂无资料</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {materials.map((material) => (
              <div key={material.id || material.filename} data-testid="catalog-material-row" className="px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="break-words text-sm font-semibold text-slate-900">{material.filename || '未命名资料'}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>{material.source_type || 'file'}</span>
                      <span>{formatFileSize(material.file_size)}</span>
                      <span>切片 {material.chunk_count ?? 0}</span>
                      <span>创建 {formatDateTime(material.created_at)}</span>
                    </div>
                    {material.last_error && (
                      <div className="mt-2 break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                        {material.last_error}
                      </div>
                    )}
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(material.status)}`}>
                      {formatMaterialStatus(material.status)}
                    </span>
                    <button
                      type="button"
                      aria-label="删除资料"
                      title="删除资料"
                      disabled={materialDeleteDisabled || deletingMaterialIds.has(material.id) || !material.id}
                      onClick={() => onDeleteMaterial(material)}
                      className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                        materialDeleteDisabled || deletingMaterialIds.has(material.id) || !material.id
                          ? 'cursor-not-allowed text-slate-300'
                          : 'text-red-500 hover:bg-red-50 hover:text-red-700'
                      }`}
                    >
                      <Icon name={deletingMaterialIds.has(material.id) ? 'progress_activity' : 'delete'} className="material-symbols-outlined text-[18px]"/>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
