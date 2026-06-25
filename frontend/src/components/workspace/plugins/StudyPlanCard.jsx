import Icon from '../../Icon';

export default function StudyPlanCard({ planDate, tasks }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2 text-slate-800 font-bold">
          <Icon name="calendar_today" className="text-cyan-600 text-[18px]" />
          <span>今日学习计划</span>
        </div>
        <span className="text-xs text-slate-400 font-mono">{planDate || '今日'}</span>
      </div>

      <div className="space-y-3">
        {tasks?.map((task, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100 hover:border-slate-200 transition-colors">
            <div className="flex items-center gap-3">
              <span className="w-6 h-6 rounded-full bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center flex-shrink-0">
                {idx + 1}
              </span>
              <span className="text-sm font-semibold text-slate-700">{task.name}</span>
            </div>
            <span className="text-xs text-slate-400 font-medium font-mono">{task.duration} 分钟</span>
          </div>
        ))}
      </div>

      <div className="mt-5 flex justify-end">
        <button className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 active:scale-95 text-white text-xs font-bold rounded-xl transition-all shadow-sm cursor-pointer flex items-center gap-1.5 border border-emerald-400">
          <Icon name="play_arrow" className="text-white text-[16px]" />
          开始练习
        </button>
      </div>
    </div>
  );
}
