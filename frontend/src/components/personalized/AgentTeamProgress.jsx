import Icon from '../Icon';

const STAGES = [
  { role: '学习规划 Leader', description: '拆解目标并协调团队', icon: 'account_tree' },
  { role: '资源生成 Agent', description: '结合课程资料生成草案', icon: 'auto_awesome' },
  { role: '确定性验证工具', description: '校验格式、引用或 OJ 结果', icon: 'fact_check' },
  { role: '独立审核 Agent', description: '宽松审核并区分硬失败与建议', icon: 'verified' },
];

export default function AgentTeamProgress({ status, message }) {
  if (status === 'idle') return null;

  const isFailed = status === 'failed';
  const isTimeout = status === 'timeout';

  const titleText = isTimeout
    ? '多智能体协作生成超时'
    : isFailed
      ? '多智能体协作生成失败'
      : '多智能体协作已启动';

  const headerColor = isFailed || isTimeout ? 'text-red-700' : 'text-cyan-800';

  return (
    <section className={`rounded-2xl border p-5 ${isFailed || isTimeout ? 'border-red-200 bg-red-50/40' : 'border-cyan-100 bg-cyan-50/40'}`} aria-label="多智能体进度">
      <div className={`mb-4 flex items-center justify-between font-semibold ${headerColor}`}>
        <div className="flex items-center gap-2">
          <Icon name={isFailed || isTimeout ? 'error' : 'groups'} className="material-symbols-outlined" />
          {titleText}
        </div>
        {message && <span className="text-xs font-normal text-slate-500">{message}</span>}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {STAGES.map((stage) => (
          <div key={stage.role} className="flex items-start gap-3 rounded-xl bg-white p-3 border border-cyan-100">
            <Icon name={stage.icon} className="material-symbols-outlined text-cyan-600" />
            <div>
              <p className="text-sm font-semibold text-slate-800">{stage.role}</p>
              <p className="text-xs text-slate-500 mt-1">{stage.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
