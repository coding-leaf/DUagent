import Icon from '../Icon';

export default function ModalityPreferenceCard({ modal_preference = {} }) {
  return (
    <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
      <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
        <Icon name="pie_chart" className="material-symbols-outlined text-cyan-500"/> 模态偏好
      </h3>
      <div className="flex flex-col gap-4">
        {[
          { key: 'video_animation', label: '视频动画' },
          { key: 'chart_logic', label: '图表逻辑' },
          { key: 'text_analysis', label: '文本分析' },
          { key: 'code_practice', label: '代码实操' },
          { key: 'formula_derivation', label: '公式推导' },
        ].map(({ key, label }) => {
          const value = modal_preference[key] ?? 0;
          const colorClass = value >= 70 ? 'bg-cyan-600' : value >= 40 ? 'bg-cyan-400' : 'bg-slate-300';
          return (
            <div key={key}>
              <div className="flex justify-between mb-1">
                <span className="text-xs text-secondary font-bold">{label}</span>
                <span className="text-xs text-cyan-700 font-bold">{value}%</span>
              </div>
              <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full ${colorClass} rounded-full transition-all`} style={{ width: `${value}%` }}></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
