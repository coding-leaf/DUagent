import Icon from '../Icon';
import FeedbackStatus from '../FeedbackStatus';

const MetricCard = ({ icon, label, value, accent = 'text-cyan-600', suffix = '' }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="mb-4 flex items-center justify-between">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <span className={`flex h-9 w-9 items-center justify-center rounded-xl bg-slate-50 ${accent}`}>
        <Icon name={icon} className="material-symbols-outlined text-lg" />
      </span>
    </div>
    <p className="text-3xl font-bold tracking-tight text-slate-900">{value}<span className="ml-1 text-sm font-medium text-slate-500">{suffix}</span></p>
  </div>
);

export default function ClassInsightsSection({ insightsLoading, insightsError, insights, studentCount, resourceCount }) {
  const weakPoints = insights?.weak_points_top ?? [];
  const pathProgress = insights?.path_node_progress ?? {};

  return (
    <section className="mb-8" aria-labelledby="class-overview-title">
      <div className="mb-4">
        <h2 id="class-overview-title" className="text-xl font-bold text-slate-900">班级概览</h2>
        <p className="mt-1 text-sm text-slate-500">快速了解当前教学班的学习参与和练习表现</p>
      </div>
      {insightsLoading ? (
        <div className="flex justify-center rounded-2xl border border-slate-200 bg-white py-10">
          <FeedbackStatus status="loading" title="加载班级统计..." />
        </div>
      ) : insightsError ? (
        <div className="flex justify-center rounded-2xl border border-slate-200 bg-white py-10">
          <FeedbackStatus status="error" title={insightsError} />
        </div>
      ) : !insights ? (
        <div className="flex justify-center rounded-2xl border border-slate-200 bg-white py-10">
          <FeedbackStatus status="empty" title="暂无班级统计数据" />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard icon="group" label="班级学生" value={studentCount} suffix="人" />
            <MetricCard icon="library_books" label="学习资源" value={resourceCount} suffix="项" accent="text-blue-600" />
            <MetricCard
              icon="quiz"
              label="平均练习分"
              value={insights.avg_quiz_score != null ? insights.avg_quiz_score.toFixed(1) : '—'}
              suffix={insights.avg_quiz_score != null ? '分' : ''}
              accent="text-emerald-600"
            />
            <MetricCard icon="assignment" label="练习次数" value={insights.total_quiz_attempts ?? 0} suffix="次" accent="text-amber-600" />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2">
                <Icon name="warning" className="material-symbols-outlined text-lg text-amber-600"/>
                <h3 className="font-bold text-slate-900">高频薄弱知识点</h3>
              </div>
              {weakPoints.length === 0 ? (
                <p className="text-sm text-slate-500">暂无薄弱知识点记录</p>
              ) : (
                <ul className="space-y-3">
                  {weakPoints.map((wp) => (
                    <li key={wp.knowledge_point} className="flex items-center justify-between gap-4 text-sm">
                      <span className="truncate font-medium text-slate-700">{wp.knowledge_point}</span>
                      <span className="shrink-0 font-bold text-red-600">错误率 {Math.round(wp.error_rate * 100)}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2">
                <Icon name="route" className="material-symbols-outlined text-lg text-cyan-600"/>
                <h3 className="font-bold text-slate-900">路径节点分布</h3>
              </div>
              {!pathProgress.total_nodes ? (
                <p className="text-sm text-slate-500">暂无学习路径数据</p>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    { label: '已完成', key: 'completed', color: 'bg-emerald-500' },
                    { label: '进行中', key: 'in_progress', color: 'bg-blue-500' },
                    { label: '推荐', key: 'recommended', color: 'bg-amber-500' },
                    { label: '待开始', key: 'pending', color: 'bg-slate-400' },
                  ].map(({ label, key, color }) => (
                    <div key={key} className="rounded-xl bg-slate-50 p-3">
                      <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                        <span className={`h-2 w-2 rounded-full ${color}`} />{label}
                      </div>
                      <p className="text-xl font-bold text-slate-900">{pathProgress[key] ?? 0}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
