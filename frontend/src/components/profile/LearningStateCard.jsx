import Icon from '../Icon';

export default function LearningStateCard({
  drive_intent = {},
  habits = {},
  driveScore,
  discipline_badge = {},
  disciplineBadgeView = {},
  labelValue,
}) {
  return (
    <div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
      <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
        <Icon name="psychology" className="material-symbols-outlined text-cyan-500"/> 学习状态
      </h3>

      {/* 驱动力 */}
      <div className="mb-6">
        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">驱动力</p>
        <div className="flex items-center gap-2 mb-3">
          <span className="px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg text-sm font-bold border border-cyan-100">
            {{
              exam_sprint: '备考冲刺',
              daily_homework: '课后巩固',
              casual: '兴趣拓展',
            }[drive_intent.type] || labelValue(drive_intent.type)}
          </span>
          {habits.label && (
            <span className={`px-3 py-1.5 rounded-lg text-sm font-bold border ${{
              new: 'bg-slate-50 text-slate-500 border-slate-200',
              inactive: 'bg-red-50 text-red-500 border-red-100',
              sprint: 'bg-orange-50 text-orange-600 border-orange-100',
              stable: 'bg-green-50 text-green-700 border-green-100',
              casual: 'bg-slate-50 text-slate-500 border-slate-200',
            }[habits.label] || 'bg-slate-50 text-slate-500 border-slate-200'}`}>
              {{
                new: '新生',
                inactive: '不活跃',
                sprint: '突击',
                stable: '稳定',
                casual: '随性',
              }[habits.label] || habits.label}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${driveScore}%` }}></div>
            </div>
          </div>
          <span className="text-xs text-slate-500 font-bold w-8 text-right">{driveScore}%</span>
        </div>
      </div>

      {/* 学科勋章 */}
      <div className="border-t border-slate-100 pt-6">
        <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">学科勋章</p>
        {discipline_badge.level ? (
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center border-4 border-amber-200">
              <Icon name="verified" className="material-symbols-outlined text-2xl text-amber-600" style={{ fontVariationSettings: '"FILL" 1' }}/>
            </div>
            <div>
              <p className="font-bold text-on-surface">
                学科勋章：{disciplineBadgeView.subject ? `${disciplineBadgeView.subject} · ` : ''}{disciplineBadgeView.level}
              </p>
              <p className="text-sm text-slate-500 mt-1">
                连续学习 <span className="text-amber-600 font-bold">{disciplineBadgeView.streakDays}</span> 天
              </p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-400 py-4 text-center">暂无学科勋章</p>
        )}
      </div>
    </div>
  );
}
