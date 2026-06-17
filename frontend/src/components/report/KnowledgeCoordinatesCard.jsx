// src/components/report/KnowledgeCoordinatesCard.jsx
import Icon from '../Icon';

/**
 * @typedef {Object} KnowledgeCoordinate
 * @property {string} name - The name of the knowledge point
 * @property {'mastered'|'learning'|'unknown'} [status] - The status of learning
 */

/**
 * Knowledge Coordinates Card Component
 * @param {Object} props
 * @param {KnowledgeCoordinate[]} props.coordinates - Array of knowledge coordinates
 */
export default function KnowledgeCoordinatesCard({ coordinates }) {
  return (
    <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="grid_view" className="material-symbols-outlined text-cyan-500"/>
        知识坐标 (Knowledge Coordinates)
      </h3>
      <div className="flex flex-wrap gap-2">
        {coordinates?.length > 0 ? (
          coordinates.map((kc) => {
            const isMastered = kc.status === 'mastered';
            const isLearning = kc.status === 'learning';
            return (
              <span key={kc.name} className={`px-3 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-1.5 ${
                isMastered ? 'bg-green-50 text-green-700 border-green-100' :
                isLearning ? 'bg-amber-50 text-amber-700 border-amber-100' :
                'bg-slate-100 text-slate-400 border-slate-200'
              }`}>
                <Icon name={isMastered ? 'check_circle' : isLearning ? 'sync' : 'help'} className="material-symbols-outlined text-sm" style={{ fontVariationSettings: '"FILL" 1' }}/>
                {kc.name}
              </span>
            );
          })
        ) : (
          <p className="text-xs text-outline italic text-center py-4">暂无知识坐标数据</p>
        )}
      </div>
    </div>
  );
}
