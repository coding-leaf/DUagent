import { Link } from 'react-router-dom';
import Icon from '../Icon';

const LANGUAGE_LABEL = {
  c: 'C',
  cpp: 'C++',
  python: 'Python',
  java: 'Java',
  go: 'Go',
  javascript: 'JavaScript',
};

const DIFFICULTY_LABEL = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
};

export default function CodeProblemResourceCard({ item, onDelete }) {
  const problem = item.code_problem;

  if (!problem) return null;

  return (
    <div className="relative group">
      <Link
        to={`/code-problems/${problem.id}`}
        className="block bg-white border border-outline-variant rounded-xl p-5 hover:shadow-md hover:border-cyan-300 hover:bg-cyan-50/5 transition-all duration-200"
      >
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-violet-50 text-violet-600 flex items-center justify-center flex-shrink-0">
            <Icon name="terminal" className="material-symbols-outlined" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-[11px] font-medium text-violet-700 bg-violet-50 px-2 py-0.5 rounded-md">
                {LANGUAGE_LABEL[problem.language] || problem.language}
              </span>
              <span className="text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md">
                {DIFFICULTY_LABEL[problem.difficulty] || problem.difficulty}
              </span>
            </div>
            <h4 className="text-body-md font-medium text-on-surface truncate">{problem.title}</h4>
            {problem.knowledge_point && (
              <p className="text-label-sm text-secondary mt-1 line-clamp-1">{problem.knowledge_point}</p>
            )}
          </div>
        </div>
      </Link>
      {onDelete && (
        <button
          className="absolute top-3 right-3 p-1.5 text-slate-400 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto hover:text-red-500 hover:bg-red-50 rounded transition-all"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onDelete(item.id);
          }}
          title="删除"
        >
          <Icon name="delete" className="material-symbols-outlined text-[20px]" />
        </button>
      )}
    </div>
  );
}
