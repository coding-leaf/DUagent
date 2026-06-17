import Icon from '../Icon';

export default function PathProgressCard({ progress }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="account_tree" className="material-symbols-outlined text-primary text-xl"/>
        学习路径进度 (Path Progress)
      </h3>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-secondary mb-1">当前学习节点</p>
          <p className="text-base font-bold text-on-surface truncate max-w-[120px]">{progress?.current_node || '暂无活跃节点'}</p>
        </div>
        <div className="flex flex-col items-end">
          <span className="text-xl font-black text-primary">
            {progress?.completed_nodes || 0} / {progress?.total_nodes || 0}
          </span>
          <span className="text-[10px] text-secondary">已完成节点</span>
        </div>
      </div>
      <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
        <div
          className="bg-primary h-full transition-all duration-300"
          style={{ width: `${((progress?.completed_nodes || 0) / (progress?.total_nodes || 1)) * 100}%` }}
        ></div>
      </div>
    </div>
  );
}
