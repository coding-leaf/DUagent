import Icon from '../../Icon';

export default function PathRecommendationCard({ strategy, duration, target, steps }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2 text-slate-800 font-bold">
          <Icon name="route" className="text-blue-500 text-[18px]" />
          <span>个性化路径推荐</span>
        </div>
        <span className="px-2 py-0.5 text-[10px] font-bold text-blue-600 bg-blue-50 border border-blue-100 rounded">
          {strategy || '补强优先'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6 bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs">
        <div>
          <span className="text-slate-400 block mb-0.5">预计时长</span>
          <span className="font-bold text-slate-700 font-mono">{duration || '15 天'}</span>
        </div>
        <div>
          <span className="text-slate-400 block mb-0.5">核心目标</span>
          <span className="font-bold text-slate-700">{target || '强化薄弱概念'}</span>
        </div>
      </div>

      <div className="flex items-center justify-between overflow-x-auto py-2 px-1 gap-2 custom-scrollbar">
        {steps?.map((step, idx) => (
          <div key={idx} className="flex items-center gap-2 flex-shrink-0">
            <div className="flex flex-col items-center">
              <span className={`w-8 h-8 rounded-full font-bold text-xs flex items-center justify-center border shadow-sm ${
                idx === 1 
                  ? 'bg-blue-500 text-white border-blue-500' 
                  : 'bg-white text-slate-400 border-slate-200'
              }`}>
                {idx + 1}
              </span>
              <span className="text-[10px] font-semibold mt-1.5 text-slate-600">{step.name}</span>
            </div>
            {idx < steps.length - 1 && (
              <span className="text-slate-300 font-bold select-none text-[16px]">→</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
