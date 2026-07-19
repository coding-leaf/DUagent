import Icon from '../Icon';

export default function MasteryDistributionCard({ masteryDistribution, totalNodes }) {
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
      <h3 className="font-h3 text-xl font-bold mb-4 flex items-center">
        <Icon name="donut_large" className="material-symbols-outlined mr-2 text-cyan-600"/>
        掌握度分布
      </h3>
      <div className="space-y-3 flex-1 flex flex-col justify-between">
        {masteryDistribution.map(group => {
          const width = totalNodes ? `${Math.round((group.count / totalNodes) * 100)}%` : '0%';
          return (
            <div key={group.key} className="space-y-1">
              <div className="flex justify-between text-sm text-slate-600">
                <span>{group.label}</span>
                <span className="font-semibold">{group.count}</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full ${group.color}`} style={{ width }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
