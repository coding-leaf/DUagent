import { Link, useNavigate } from 'react-router-dom';

const assessmentLabels = {
  scored: '已评估',
  mastered: '已掌握',
  weak: '薄弱',
  learning: '学习中',
  pending_practice: '待练习',
  unstarted: '未开始',
  unassessed_default_pass: '未测评/默认通过',
  unknown: '暂无数据',
};

const assessmentStyles = {
  scored: 'bg-emerald-50 text-emerald-700',
  mastered: 'bg-emerald-50 text-emerald-700',
  weak: 'bg-red-50 text-red-700',
  learning: 'bg-cyan-50 text-cyan-700',
  pending_practice: 'bg-amber-50 text-amber-700',
  unstarted: 'bg-slate-100 text-slate-600',
  unassessed_default_pass: 'bg-slate-100 text-slate-600',
  unknown: 'bg-gray-100 text-gray-500',
};

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '暂无记录';
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}分钟`;
  return `${(minutes / 60).toFixed(1)}小时`;
}

function getMasteryDisplay(row) {
  if (row.mastery_score !== null && row.mastery_score !== undefined) {
    return `${Math.round(row.mastery_score)}%`;
  }
  return row.mastery_label || assessmentLabels[row.assessment_state] || '暂无数据';
}

export default function KnowledgeProgressTable({ nodeRows, activeCourseId }) {
  const navigate = useNavigate();

  return (
    <section className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-6">
        <h3 className="font-h3 text-xl font-bold">KG 节点学习进度</h3>
        <span className="text-sm text-slate-400">无题节点不计入真实均分</span>
      </div>

      {nodeRows.length === 0 ? (
        <div className="py-12 text-center text-slate-500">
          课程知识图谱尚未准备好，或当前课程暂无学习效果记录。
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[820px]">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="pb-3 text-sm text-slate-400">节点名称</th>
                <th className="pb-3 text-sm text-slate-400">学习状态</th>
                <th className="pb-3 text-sm text-slate-400">学习耗时</th>
                <th className="pb-3 text-sm text-slate-400">掌握评分</th>
                <th className="pb-3 text-sm text-slate-400">证据来源</th>
                <th className="pb-3 text-sm text-slate-400">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {nodeRows.map(row => (
                <tr key={row.node_id} className="group hover:bg-slate-50 transition-colors">
                  <td className="py-4 font-body-md text-slate-700">{row.node_name}</td>
                  <td className="py-4">
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${assessmentStyles[row.assessment_state] || assessmentStyles.unknown}`}>
                      {row.status || assessmentLabels[row.assessment_state] || '暂无数据'}
                    </span>
                  </td>
                  <td className="py-4 font-body-md text-slate-500">{formatDuration(row.study_duration_seconds)}</td>
                  <td className="py-4 font-bold text-cyan-600">{getMasteryDisplay(row)}</td>
                  <td className="py-4 text-sm text-slate-500">
                    {row.hasPracticeEvidence
                      ? `${row.attempt_count || 0} 次答题 / ${row.question_count || 0} 题`
                      : row.assessment_state === 'pending_practice'
                        ? `${row.question_count || 0} 题待练习`
                        : '暂无题目'}
                  </td>
                  <td className="py-4">
                    <div className="flex flex-wrap gap-2">
                      {row.question_count > 0 && (
                        <button
                          onClick={() => navigate(`/quiz?course_id=${activeCourseId}&node_id=${row.node_id}`)}
                          className="px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg text-xs font-bold hover:bg-cyan-100"
                        >
                          进入练习
                        </button>
                      )}
                      <Link to="/learning-path" className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-200">
                        查看资源
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
