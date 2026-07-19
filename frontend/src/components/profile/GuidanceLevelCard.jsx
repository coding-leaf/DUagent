import Icon from '../Icon';

export default function GuidanceLevelCard({
  localGuidanceLevel,
  handleGuidanceChange,
  guidanceSubmitting,
  guidanceUpdatedText,
}) {
  return (
    <div className="lg:col-span-8 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm flex flex-col">
      <div className="mb-8">
        <h3 className="font-h3 text-xl mb-4 flex items-center gap-2 text-on-surface">
          <Icon name="tune" className="material-symbols-outlined text-cyan-500"/> 引导粒度
        </h3>
        <p className="text-body-md text-secondary">根据当前任务难度与心流状态，动态调整智能体的介入深度。</p>
        <p className="text-sm text-cyan-600 font-bold mt-2">
          当前等级：{['L1', 'L2', 'L3'].includes(localGuidanceLevel) ? localGuidanceLevel : '未知'}
        </p>
      </div>
      <div className="relative px-6 py-12 flex-1">
        <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden relative">
          <div className="h-full bg-gradient-to-r from-cyan-400 to-cyan-600 transition-all duration-500 ease-out" style={{ width: `${
            localGuidanceLevel === 'L1' ? '0%' :
            localGuidanceLevel === 'L2' ? '50%' :
            localGuidanceLevel === 'L3' ? '100%' : '50%'
          }` }}></div>
        </div>
        <div className="flex justify-between items-center absolute w-full left-0 top-0 mt-[38px] px-4">
          <button
            className="flex flex-col items-center cursor-pointer disabled:opacity-50 bg-transparent border-0 p-0"
            onClick={() => handleGuidanceChange('L1')}
            disabled={guidanceSubmitting}
          >
            <div className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 transition-colors duration-300 ${
              localGuidanceLevel === 'L1'
                ? 'bg-cyan-500 border-white shadow-cyan-200'
                : 'bg-white border-slate-200 hover:border-cyan-300'
            }`}></div>
            <div className="mt-6 text-center">
              <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L1' ? 'text-cyan-600' : 'text-slate-400'}`}>L1: 启发点拨</p>
              <p className="text-[10px] text-slate-400 mt-1">核心思路提示</p>
            </div>
          </button>
          <button
            className="flex flex-col items-center cursor-pointer disabled:opacity-50 bg-transparent border-0 p-0"
            onClick={() => handleGuidanceChange('L2')}
            disabled={guidanceSubmitting}
          >
            <div className={`w-10 h-10 rounded-full border-[6px] shadow-xl z-20 transition-colors duration-300 ${
              localGuidanceLevel === 'L2'
                ? 'bg-cyan-500 border-white shadow-cyan-200'
                : 'bg-white border-slate-200 shadow-sm hover:border-cyan-300'
            }`}></div>
            <div className="mt-4 text-center">
              <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L2' ? 'text-cyan-600' : 'text-slate-400'}`}>L2: 伴学拆解</p>
              <p className={`text-[10px] transition-colors duration-300 ${localGuidanceLevel === 'L2' ? 'text-cyan-400' : 'text-slate-400'} mt-1`}>分步引导学习</p>
            </div>
          </button>
          <button
            className="flex flex-col items-center cursor-pointer disabled:opacity-50 bg-transparent border-0 p-0"
            onClick={() => handleGuidanceChange('L3')}
            disabled={guidanceSubmitting}
          >
            <div className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 transition-colors duration-300 ${
              localGuidanceLevel === 'L3'
                ? 'bg-cyan-500 border-white shadow-cyan-200'
                : 'bg-white border-slate-200 hover:border-cyan-300'
            }`}></div>
            <div className="mt-6 text-center">
              <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L3' ? 'text-cyan-600' : 'text-slate-400'}`}>L3: 逐步指导</p>
              <p className="text-[10px] text-slate-400 mt-1">全自动代码生成</p>
            </div>
          </button>
        </div>
      </div>
      {guidanceUpdatedText && (
        <p className="text-xs text-slate-400 mt-4 text-center">
          更新于 {guidanceUpdatedText}
        </p>
      )}
    </div>
  );
}
