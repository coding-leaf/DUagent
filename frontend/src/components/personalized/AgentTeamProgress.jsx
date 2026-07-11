import Icon from '../Icon';

const STAGES = [
  { role: '学习规划 Leader', description: '拆解目标并协调团队', icon: 'account_tree' },
  { role: '资源生成 Agent', description: '结合课程资料生成草案', icon: 'auto_awesome' },
  { role: '确定性验证工具', description: '校验格式、引用或 OJ 结果', icon: 'fact_check' },
  { role: '独立审核 Agent', description: '宽松审核并区分硬失败与建议', icon: 'verified' },
];

export default function AgentTeamProgress({ status }) {
  if (status === 'idle') return null;
  return (
    <section className="rounded-2xl border border-cyan-100 bg-cyan-50/40 p-5" aria-label="多智能体进度">
      <div className="mb-4 flex items-center gap-2 text-cyan-800 font-semibold">
        <Icon name="groups" className="material-symbols-outlined" />
        多智能体协作已启动
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
