import Icon from '../../Icon';

export default function WeakPointsCard({ title, points }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2 text-slate-800 font-bold">
          <Icon name="broken_image" className="text-amber-500 text-[18px]" />
          <span>{title || '薄弱点分析'}</span>
        </div>
      </div>

      <div className="space-y-4">
        {points?.map((item, idx) => {
          let barColor = 'bg-emerald-500';
          let textColor = 'text-emerald-700 bg-emerald-50 border-emerald-100';
          let impactText = '低';

          if (item.mastery < 45) {
            barColor = 'bg-red-500';
            textColor = 'text-red-700 bg-red-50 border-red-100';
            impactText = '高';
          } else if (item.mastery < 70) {
            barColor = 'bg-amber-500';
            textColor = 'text-amber-700 bg-amber-50 border-amber-100';
            impactText = '中';
          }

          return (
            <div key={idx} className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">{item.name}</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-400">掌握度: {item.mastery}%</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] border font-bold ${textColor}`}>
                    影响: {impactText}
                  </span>
                </div>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div className={`${barColor} h-full rounded-full transition-all duration-500`} style={{ width: `${item.mastery}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
