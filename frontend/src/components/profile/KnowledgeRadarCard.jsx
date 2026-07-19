import Icon from '../Icon';

export default function KnowledgeRadarCard({
  knowledge_coordinates = [],
  cognitive_blindspots = [],
  daysAgoText,
  labelValue,
}) {
  return (
    <div className="lg:col-span-7 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
      <h3 className="font-h3 text-xl mb-8 flex items-center gap-2 text-on-surface">
        <Icon name="grid_view" className="material-symbols-outlined text-cyan-500"/> 知识坐标 &amp; 认知盲区
      </h3>

      {/* 上半：知识坐标 */}
      <div className="mb-6">
        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">知识坐标</p>
        {knowledge_coordinates.length > 0 ? (
          <div className="flex flex-wrap gap-3">
            {knowledge_coordinates.map((node, i) => {
              const state = node.status || 'unstarted';
              const stateConfig = {
                mastered: {
                  color: 'bg-green-50 text-green-700 border-green-100',
                  icon: 'check_circle',
                  label: '已掌握',
                },
                weak: {
                  color: 'bg-red-50 text-red-700 border-red-100',
                  icon: 'warning',
                  label: '薄弱',
                },
                learning: {
                  color: 'bg-amber-50 text-amber-700 border-amber-100',
                  icon: 'sync',
                  label: '学习中',
                },
                pending_practice: {
                  color: 'bg-cyan-50 text-cyan-700 border-cyan-100',
                  icon: 'quiz',
                  label: '待练习',
                },
                unstarted: {
                  color: 'bg-slate-100 text-slate-500 border-slate-200',
                  icon: 'radio_button_unchecked',
                  label: '未开始',
                },
              }[state] || {
                color: 'bg-slate-100 text-slate-500 border-slate-200',
                icon: 'help',
                label: labelValue(state) || '未知',
              };
              return (
                <span
                  key={i}
                  className={`px-4 py-2 rounded-lg border text-sm font-bold flex items-center gap-2 transition-all hover:scale-105 ${stateConfig.color}`}
                >
                  <Icon name={stateConfig.icon} className="material-symbols-outlined text-base" style={{ fontVariationSettings: '"FILL" 1' }}/>
                  {node.name}
                  <span className="text-xs font-normal opacity-60">{stateConfig.label}</span>
                  {state === 'mastered' && node.mastered_at && (
                    <span className="text-green-400 text-xs font-normal ml-1">
                      · {daysAgoText(node.mastered_at, '掌握')}
                    </span>
                  )}
                </span>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-400 py-8 text-center">暂无知识坐标数据</p>
        )}
      </div>

      {/* 下半：认知盲区 */}
      <div className="border-t border-slate-100 pt-6">
        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">认知盲区</p>
        {cognitive_blindspots.length > 0 ? (
          <div className="space-y-2">
            {cognitive_blindspots.map((item, i) => {
              const blindspot = typeof item === 'string' ? { name: item } : item;
              const severityColors = {
                high: 'bg-red-50 text-red-700 border-red-100',
                medium: 'bg-amber-50 text-amber-700 border-amber-100',
                low: 'bg-slate-100 text-slate-500 border-slate-200',
              };
              const severityLabels = { high: '高', medium: '中', low: '低' };
              const colorClass = severityColors[blindspot.severity] || 'bg-slate-100 text-slate-500 border-slate-200';
              const label = severityLabels[blindspot.severity] || blindspot.severity || '待关注';
              return (
                <div key={i} className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${colorClass} border`}>
                    {label}
                  </span>
                  <span className="text-sm text-on-surface">{blindspot.name || blindspot.point || '未命名薄弱点'}</span>
                  {blindspot.error_count !== undefined && (
                    <span className="text-xs text-slate-400">· 错误 {blindspot.error_count} 次</span>
                  )}
                  {blindspot.source === 'profile_dialogue' && (
                    <span className="text-xs text-cyan-600">· 对话补充</span>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-400 py-4 text-center">暂无认知盲区记录</p>
        )}
      </div>
    </div>
  );
}
