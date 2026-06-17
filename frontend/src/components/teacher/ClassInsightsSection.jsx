import Icon from '../Icon';
import FeedbackStatus from '../FeedbackStatus';

export default function ClassInsightsSection({ insightsLoading, insightsError, insights }) {
  return (
    <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-margin">
      {insightsLoading ? (
        <div className="col-span-full py-8 flex justify-center">
          <FeedbackStatus status="loading" title="加载班级统计..." />
        </div>
      ) : insightsError ? (
        <div className="col-span-full py-8 flex justify-center">
          <FeedbackStatus status="error" title={insightsError} />
        </div>
      ) : !insights ? (
        <div className="col-span-full py-8 flex justify-center">
          <FeedbackStatus status="empty" title="暂无班级统计数据" />
        </div>
      ) : (
        <>
          {/* Avg Quiz Score */}
          <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
            <div className="flex items-center gap-2 mb-3">
              <Icon name="quiz" className="material-symbols-outlined text-primary text-xl"/>
              <span className="text-sm font-semibold text-outline">平均练习分</span>
            </div>
            <p className="text-3xl font-bold text-on-surface">
              {insights.avg_quiz_score != null
                ? insights.avg_quiz_score.toFixed(1)
                : '暂无数据'}
            </p>
          </div>

          {/* Total Quiz Attempts */}
          <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
            <div className="flex items-center gap-2 mb-3">
              <Icon name="assignment" className="material-symbols-outlined text-primary text-xl"/>
              <span className="text-sm font-semibold text-outline">练习次数</span>
            </div>
            <p className="text-3xl font-bold text-on-surface">
              {insights.total_quiz_attempts}
            </p>
          </div>

          {/* Weak Points Top */}
          <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md md:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2 mb-3">
              <Icon name="warning" className="material-symbols-outlined text-error text-xl"/>
              <span className="text-sm font-semibold text-outline">薄弱知识点</span>
            </div>
            {insights.weak_points_top.length === 0 ? (
              <p className="text-sm text-outline">暂无薄弱知识点</p>
            ) : (
              <ul className="space-y-2">
                {insights.weak_points_top.map((wp) => (
                  <li key={wp.knowledge_point} className="text-sm">
                    <div className="flex justify-between items-center">
                      <span className="text-on-surface truncate max-w-[60%]">{wp.knowledge_point}</span>
                      <span className="text-error font-semibold">{Math.round(wp.error_rate * 100)}%</span>
                    </div>
                    <span className="text-xs text-outline">
                      错 {wp.error_count} / 共 {wp.total_attempts} 次
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Path Node Progress */}
          <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
            <div className="flex items-center gap-2 mb-3">
              <Icon name="route" className="material-symbols-outlined text-primary text-xl"/>
              <span className="text-sm font-semibold text-outline">路径节点分布</span>
            </div>
            {insights.path_node_progress.total_nodes === 0 ? (
              <p className="text-sm text-outline">暂无学习路径数据</p>
            ) : (
              <div className="space-y-2">
                {[
                  { label: '已完成', key: 'completed', color: 'bg-green-500' },
                  { label: '进行中', key: 'in_progress', color: 'bg-blue-500' },
                  { label: '推荐', key: 'recommended', color: 'bg-amber-500' },
                  { label: '待开始', key: 'pending', color: 'bg-gray-400' },
                ].map(({ label, key, color }) => (
                  <div key={key} className="flex items-center gap-2 text-sm">
                    <div className={`w-2.5 h-2.5 rounded-full ${color}`} />
                    <span className="text-on-surface-variant w-14">{label}</span>
                    <span className="font-semibold text-on-surface">{insights.path_node_progress[key]}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
