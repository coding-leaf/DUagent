// src/components/report/MasteryBreakdownCard.jsx
import Icon from '../Icon';

/**
 * @typedef {Object} MasteryBreakdownItem
 * @property {string} knowledge_point - The name of the knowledge point
 * @property {number} accuracy - The accuracy percentage
 */

/**
 * Mastery Breakdown Card Component
 * @param {Object} props
 * @param {MasteryBreakdownItem[]} props.breakdown - Array of mastery breakdown items
 */
export default function MasteryBreakdownCard({ breakdown }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="assessment" className="material-symbols-outlined text-primary text-xl"/>
        练习掌握度 (Mastery Breakdown)
      </h3>
      {breakdown?.length > 0 ? (
        <div className="space-y-3">
          {breakdown.map((item) => (
            <div key={item.knowledge_point} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="font-medium text-on-surface">{item.knowledge_point}</span>
                <span className="font-bold text-primary">{item.accuracy}%</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${item.accuracy}%` }}></div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-outline italic text-center py-4">暂无练习数据</p>
      )}
    </div>
  );
}
