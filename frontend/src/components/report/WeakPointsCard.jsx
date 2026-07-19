import Icon from '../Icon';

/**
 * @typedef {Object} WeakPoint
 * @property {string} knowledge_point
 * @property {number} error_count
 * @property {number} total_attempts
 * @property {number} error_rate
 *
 * @typedef {Object} Summary
 * @property {number} knowledge_mastered
 * @property {number} knowledge_weak
 *
 * @param {Object} props
 * @param {WeakPoint[]} props.weakPoints
 * @param {Summary} props.summary
 */
export default function WeakPointsCard({ weakPoints, summary }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-6 flex flex-col justify-between">
      <div>
        <h3 className="text-base font-bold text-on-surface mb-2 flex items-center gap-2">
          <Icon name="local_fire_department" className="material-symbols-outlined text-orange-500"/>
          薄弱知识点 (Weak Points)
        </h3>
        <div className="flex flex-wrap gap-2 mt-3">
          {Array.isArray(weakPoints) && weakPoints.length > 0 ? (
            weakPoints.map((wp) => (
              <div key={wp.knowledge_point} className="px-3 py-2 bg-orange-50 rounded-lg border border-orange-100 text-xs">
                <span className="font-bold text-orange-700">{wp.knowledge_point}</span>
                <span className="text-orange-500 ml-2">
                  {wp.error_count || 0}/{wp.total_attempts || 0} 错 ({Math.round((wp.error_rate || 0) * 100)}%)
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-outline italic">暂无薄弱点</p>
          )}
        </div>
      </div>

      <div className="pt-4 border-t border-slate-50 grid grid-cols-2 gap-4">
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
          <span className="text-xl font-bold text-green-600 block">{summary?.knowledge_mastered || 0}</span>
          <span className="text-[10px] text-secondary">已掌握知识点</span>
        </div>
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
          <span className="text-xl font-bold text-orange-600 block">{summary?.knowledge_weak || 0}</span>
          <span className="text-[10px] text-secondary">薄弱知识点数</span>
        </div>
      </div>
    </div>
  );
}
