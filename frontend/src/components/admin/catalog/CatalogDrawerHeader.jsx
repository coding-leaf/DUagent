import Icon from '../../Icon';
import { getBadgeClass, formatCatalogStatus, formatKnowledgeStatus } from './formatters';

export default function CatalogDrawerHeader({ catalog, knowledgeStatus, onClose }) {
  return (
    <header className="border-b border-slate-200 px-6 py-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="mb-1 text-xs font-bold text-slate-400">课程资源库详情</p>
          <h2 className="break-words text-xl font-bold text-slate-900">{catalog.title || '未命名资源库'}</h2>
          <p className="mt-1 break-words text-sm text-slate-500">{catalog.description || '暂无描述'}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
          title="关闭"
        >
          <Icon name="close" className="material-symbols-outlined text-[20px]"/>
        </button>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <span className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(knowledgeStatus?.status || catalog.status)}`}>
          资源库 {formatCatalogStatus(knowledgeStatus?.status || catalog.status)}
        </span>
        <span className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(knowledgeStatus?.knowledge_status || catalog.knowledge_status)}`}>
          知识库 {formatKnowledgeStatus(knowledgeStatus?.knowledge_status || catalog.knowledge_status)}
        </span>
      </div>
    </header>
  );
}
