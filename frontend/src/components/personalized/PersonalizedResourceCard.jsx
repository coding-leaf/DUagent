import { Link } from 'react-router-dom';

import Icon from '../Icon';
import { PERSONALIZED_TYPE_META } from './resourceTypes';

const LEGACY_TYPE_META = {
  lesson: PERSONALIZED_TYPE_META.personal_lesson,
  document: PERSONALIZED_TYPE_META.personal_lesson,
  mindmap: PERSONALIZED_TYPE_META.diagram,
  example: PERSONALIZED_TYPE_META.validated_code_problem,
  code: PERSONALIZED_TYPE_META.validated_code_problem,
};

const SOURCE_LABEL = {
  quiz_wrong_answer: '错题复习',
  manual: '手动生成',
  ai_chat: 'AI 对话',
  learning_effects: '学情建议',
};

const REVIEW_LABEL = {
  approved: '审核通过',
  approved_with_advice: '审核通过',
  rejected: '审核未通过',
};

export default function PersonalizedResourceCard({ item, onDelete }) {
  if (item.task_status === 'processing') {
    return (
      <StatusCard
        icon="progress_activity"
        title="多智能体正在协作生成"
        spinning
        onDelete={onDelete ? () => onDelete(item.id) : undefined}
      />
    );
  }
  if (item.task_status === 'failed') {
    return (
      <StatusCard
        icon="error"
        title="生成失败"
        tone="error"
        onDelete={onDelete ? () => onDelete(item.id) : undefined}
      />
    );
  }
  if (!item.resource) return null;

  const resource = item.resource;
  const type = item.resource_type || resource.type;
  const meta = PERSONALIZED_TYPE_META[type] || LEGACY_TYPE_META[type] || {
    label: '学习资料',
    icon: 'article',
  };

  return (
    <div className="relative group bg-white border border-outline-variant rounded-xl hover:border-cyan-300 hover:shadow-md transition-all">
      <Link to={`/resource/${resource.id}`} className="block p-5">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-cyan-50 text-cyan-700 flex items-center justify-center flex-shrink-0">
            <Icon name={meta.icon} className="material-symbols-outlined" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap gap-2 mb-2 text-[11px]">
              <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded-md">{meta.label}</span>
              <span className="bg-cyan-50 text-cyan-700 px-2 py-0.5 rounded-md">
                {SOURCE_LABEL[item.source_type] || item.source_type}
              </span>
              {item.review_decision && (
                <span className="bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-md">
                  {REVIEW_LABEL[item.review_decision] || item.review_decision}
                </span>
              )}
            </div>
            <h4 className="text-body-md font-medium text-on-surface truncate">{resource.title}</h4>
            {resource.description && <p className="text-label-sm text-secondary mt-1 line-clamp-2">{resource.description}</p>}
          </div>
        </div>
      </Link>
      {onDelete && (
        <button
          type="button"
          onClick={() => onDelete(item.id)}
          className="absolute top-3 right-3 p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500"
          aria-label="删除资源"
        >
          <Icon name="delete" className="material-symbols-outlined text-[20px]" />
        </button>
      )}
    </div>
  );
}

function StatusCard({ icon, title, tone = 'info', spinning = false, onDelete }) {
  const color = tone === 'error' ? 'text-error border-error/20' : 'text-cyan-700 border-cyan-200';
  return (
    <div className={`relative group bg-white border border-dashed rounded-xl p-5 flex items-center gap-4 ${color}`}>
      <Icon name={icon} className={`material-symbols-outlined ${spinning ? 'animate-spin' : ''}`} />
      <p className="text-body-md font-medium">{title}</p>
      {onDelete && (
        <button
          type="button"
          onClick={onDelete}
          className="absolute top-3 right-3 p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-colors cursor-pointer"
          aria-label="清除任务"
        >
          <Icon name="delete" className="material-symbols-outlined text-[20px]" />
        </button>
      )}
    </div>
  );
}
