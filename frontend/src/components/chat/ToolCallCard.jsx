import Icon from '../Icon';
export default function ToolCallCard({ name, status }) {
  const isRunning = status === 'running';

  return (
    <div className="flex items-center gap-2 text-slate-500 text-[13px] mb-3">
      {isRunning ? (
        <span className="inline-block w-3.5 h-3.5 rounded-full border-2 border-slate-300 border-t-slate-500 animate-spin"></span>
      ) : (
        <Icon name="check_circle" className="material-symbols-outlined text-[16px] text-emerald-500"/>
      )}
      <span>{name || '正在检索知识库...'}</span>
    </div>
  );
}
