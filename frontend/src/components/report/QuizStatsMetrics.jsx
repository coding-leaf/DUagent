import Icon from '../Icon';

/**
 * @param {{ stats: { total_attempts?: number, avg_score?: number, avg_time_spent?: number } }} props
 */
export default function QuizStatsMetrics({ stats }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="assessment" className="material-symbols-outlined text-primary text-xl"/>
        在线测试统计 (Quiz Stats)
      </h3>
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-surface-container rounded p-3 text-center">
          <span className="text-xl font-bold text-on-surface block">{stats?.total_attempts || 0}</span>
          <span className="text-[10px] text-secondary">总测试</span>
        </div>
        <div className="bg-surface-container rounded p-3 text-center">
          <span className="text-xl font-bold text-on-surface block">{stats?.avg_score || 0}%</span>
          <span className="text-[10px] text-secondary">平均分</span>
        </div>
        <div className="bg-surface-container rounded p-3 text-center">
          <span className="text-xl font-bold text-on-surface block">{!stats?.total_attempts ? '-' : (stats?.avg_time_spent < 60 ? '< 1m' : `${Math.round((stats.avg_time_spent) / 60)}m`)}</span>
          <span className="text-[10px] text-secondary">均时</span>
        </div>
      </div>
    </div>
  );
}
