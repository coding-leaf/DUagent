import Icon from '../Icon';

export default function ModalityPreferenceCard({ preferences }) {
  const modalLabels = { video_animation: '视频/动画', chart_logic: '图表/逻辑', text_analysis: '文本阅读', code_practice: '代码练习', formula_derivation: '公式推导' };
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
      <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
        <Icon name="psychology" className="material-symbols-outlined text-primary text-xl"/>
        模态偏好 (Modal Preference)
      </h3>
      <div className="flex flex-wrap gap-2">
        {preferences && preferences.length > 0 ? (
          preferences.map((p, idx) => (
            <span key={idx} className="px-3 py-1.5 bg-cyan-50 text-cyan-700 text-xs font-bold rounded-lg border border-cyan-100 flex items-center gap-1">
              <span className="text-[10px] opacity-60">#{idx + 1}</span> {modalLabels[p] || p}
            </span>
          ))
        ) : (
          <p className="text-xs text-outline italic text-center py-4">暂无偏好数据</p>
        )}
      </div>
    </div>
  );
}
