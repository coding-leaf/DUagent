import Icon from '../Icon';

/**
 * @typedef {Object} Activity
 * @property {number} [id]
 * @property {string} chapter
 * @property {string} created_at
 * @property {number} score
 * @property {number} correct_count
 * @property {number} total_count
 *
 * @param {Object} props
 * @param {Activity[]} props.activity
 */
export default function RecentActivityCard({ activity }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="timeline" className="material-symbols-outlined text-primary text-xl"/>
        最近学习活动 (Recent Activity)
      </h3>
      <div className="space-y-4 max-h-[220px] overflow-y-auto pr-2 scrollbar-thin">
        {Array.isArray(activity) && activity.length > 0 ? (
          activity.map((ra, i) => (
            <div key={ra.id || `${ra.chapter}-${ra.created_at}-${i}`} className="flex items-center gap-3 pb-3 border-b border-slate-50 last:border-0">
              <div className="w-8 h-8 rounded-full bg-cyan-100 flex items-center justify-center flex-shrink-0">
                <Icon name="exercise" className="material-symbols-outlined text-cyan-600 text-sm"/>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-on-surface truncate">{ra.chapter || '练习'}</p>
                <p className="text-[10px] text-outline">
                  {ra.created_at ? new Date(ra.created_at).toLocaleDateString('zh-CN') : ''}
                </p>
              </div>
              <div className="text-right flex-shrink-0">
                <span className="text-sm font-bold text-primary">{Math.round(ra.score || 0)}%</span>
                <p className="text-[10px] text-outline">{ra.correct_count || 0}/{ra.total_count || 0} 正确</p>
              </div>
            </div>
          ))
        ) : (
          <p className="text-xs text-outline italic text-center py-8">暂无近期活动</p>
        )}
      </div>
    </div>
  );
}
