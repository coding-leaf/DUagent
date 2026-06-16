import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { profileService } from '../api/services/profile';
import { learningService } from '../api/services/learning';
import { taskService } from '../api/services/task';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import Icon from '../components/Icon';

const terminalTaskStates = new Set(['completed', 'failed', 'partial']);

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

function hasPracticeEvidence(row) {
  return Number(row.attempt_count || 0) > 0
    || ['scored', 'mastered', 'weak'].includes(row.assessment_state);
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '暂无记录';
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}分钟`;
  return `${(minutes / 60).toFixed(1)}小时`;
}

function formatDate(value) {
  if (!value) return '尚未生成';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '尚未生成';
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function normalizeRows(data) {
  if (Array.isArray(data?.node_progress)) return data.node_progress;
  if (Array.isArray(data?.progress_table?.rows)) {
    return data.progress_table.rows.filter(row => row?.node_id && row?.node_name);
  }
  return [];
}

function getMasteryDisplay(row) {
  if (row.mastery_score !== null && row.mastery_score !== undefined) {
    return `${Math.round(row.mastery_score)}%`;
  }
  return row.mastery_label || assessmentLabels[row.assessment_state] || '暂无数据';
}

export default function LearningEffects() {
  const navigate = useNavigate();
  const { activeCourseId } = useCourse();
  const [effectsData, setEffectsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [refreshTask, setRefreshTask] = useState(null);

  const loadEffects = useCallback(async () => {
    if (!activeCourseId) {
      setEffectsData(null);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await profileService.getLearningEffects(activeCourseId);
      if (res.code === 200) {
        setEffectsData(res.data);
      } else {
        setError(res.message || '学习效果加载失败');
      }
    } catch (err) {
      console.error('学习效果加载失败:', err);
      setError('学习效果加载失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [activeCourseId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      loadEffects();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadEffects]);

  useEffect(() => {
    if (!refreshTask?.task_id || terminalTaskStates.has(refreshTask.status)) return undefined;

    const timer = window.setInterval(async () => {
      try {
        const res = await taskService.getTaskStatus(refreshTask.task_id);
        if (res.code !== 200 || !res.data) return;
        const nextTask = res.data;
        setRefreshTask(nextTask);
        if (terminalTaskStates.has(nextTask.status)) {
          window.clearInterval(timer);
          if (nextTask.status === 'completed') {
            await loadEffects();
          }
        }
      } catch (err) {
        console.error('学习效果刷新任务查询失败:', err);
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [refreshTask?.task_id, refreshTask?.status, loadEffects]);

  const nodeRows = useMemo(() => normalizeRows(effectsData), [effectsData]);

  const overview = useMemo(() => ({
    total: nodeRows.length,
    practiced: nodeRows.filter(hasPracticeEvidence).length,
    pending: nodeRows.filter(row => row.assessment_state === 'pending_practice').length,
    defaultPass: nodeRows.filter(row => (
      row.assessment_state === 'unassessed_default_pass'
      || row.assessment_state === 'unstarted'
    )).length,
  }), [nodeRows]);

  const masteryDistribution = useMemo(() => {
    const groups = [
      { key: 'A', label: 'A / 高掌握', count: 0, color: 'bg-emerald-500' },
      { key: 'B', label: 'B / 基本掌握', count: 0, color: 'bg-cyan-500' },
      { key: 'C', label: 'C / 需复习', count: 0, color: 'bg-orange-500' },
      { key: 'weak', label: '薄弱', count: 0, color: 'bg-red-500' },
      { key: 'learning', label: '学习中', count: 0, color: 'bg-cyan-300' },
      { key: 'pending_practice', label: '待练习', count: 0, color: 'bg-amber-400' },
      { key: 'unstarted', label: '未开始', count: 0, color: 'bg-slate-400' },
    ];
    const byKey = Object.fromEntries(groups.map(group => [group.key, group]));

    nodeRows.forEach((row) => {
      if (row.assessment_state === 'pending_practice') {
        byKey.pending_practice.count += 1;
      } else if (row.assessment_state === 'unassessed_default_pass' || row.assessment_state === 'unstarted') {
        byKey.unstarted.count += 1;
      } else if (row.assessment_state === 'weak') {
        byKey.weak.count += 1;
      } else if (row.assessment_state === 'learning') {
        byKey.learning.count += 1;
      } else if (row.mastery_label === 'A') {
        byKey.A.count += 1;
      } else if (row.mastery_label === 'B') {
        byKey.B.count += 1;
      } else if (row.mastery_label === 'C' || row.mastery_label === '需复习') {
        byKey.C.count += 1;
      }
    });

    return groups;
  }, [nodeRows]);

  const handleRefresh = async () => {
    if (!activeCourseId || refreshTask?.status === 'processing') return;
    setError('');
    setRefreshTask({ status: 'processing', progress: 0 });
    try {
      const res = await learningService.refreshEvaluation(activeCourseId);
      if (res.code === 202 && res.data?.task_id) {
        setRefreshTask({ task_id: res.data.task_id, status: 'processing', progress: 0 });
      } else {
        setRefreshTask(null);
        setError(res.message || '重新评估启动失败');
      }
    } catch (err) {
      console.error('重新评估启动失败:', err);
      setRefreshTask(null);
      setError('重新评估启动失败，请稍后重试');
    }
  };

  const refreshInProgress = refreshTask?.status === 'processing';
  const refreshFailed = refreshTask && terminalTaskStates.has(refreshTask.status) && refreshTask.status !== 'completed';
  const refreshFailureMessage = refreshTask?.error_message
    || (refreshTask?.error_code ? `错误码：${refreshTask.error_code}` : '')
    || '重新评估未完整完成，当前页面保留最近一次可用评估。';

  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen">
      <Navbar />

      <aside className="h-full w-64 fixed left-0 top-16 bg-white border-r border-gray-100 flex flex-col py-6 space-y-2 font-['Public_Sans'] text-sm hidden lg:flex">
        <div className="px-6 mb-6">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center text-white">
              <Icon name="monitoring" className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}/>
            </div>
            <div>
              <h3 className="text-lg font-black text-cyan-600 leading-tight">学习效果</h3>
              <p className="text-[10px] text-gray-400 uppercase tracking-widest">KG NODE PROGRESS</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1">
          <div className="px-4">
            <Link to="/learning-path" className="flex items-center space-x-3 px-4 py-3 rounded-lg text-gray-500 hover:bg-gray-50 transition-all duration-200 ease-in-out cursor-pointer hover:pl-5">
              <Icon name="account_tree" className="material-symbols-outlined"/>
              <span className="font-body-md">学习节点</span>
            </Link>
            <Link to="/dashboard" className="flex items-center space-x-3 px-4 py-3 rounded-lg text-gray-500 hover:bg-gray-50 transition-all duration-200 ease-in-out cursor-pointer hover:pl-5">
              <Icon name="library_books" className="material-symbols-outlined"/>
              <span className="font-body-md">资源库</span>
            </Link>
          </div>
        </nav>
      </aside>

      <main className="lg:pl-64 pt-24 pb-12 px-6 max-w-[1280px] mx-auto min-h-screen">
        <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="font-h1 text-h1 text-on-surface text-4xl font-bold mb-2">学习效果展示</h1>
            <p className="text-body-md text-outline mt-2 text-slate-500">基于课程知识图谱、练习记录和评估快照的节点掌握情况</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleRefresh}
              disabled={!activeCourseId || refreshInProgress}
              className="flex items-center px-4 py-2 bg-primary-container text-on-primary-container rounded-xl font-label-sm text-label-sm font-bold shadow-sm hover:brightness-110 active:scale-95 transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Icon name="refresh" className="material-symbols-outlined mr-2"/>
              {refreshInProgress ? '评估中' : '重新评估'}
            </button>
          </div>
        </div>

        {!activeCourseId && (
          <div className="bg-white border border-gray-100 rounded-xl p-8 text-center text-slate-500">
            请先加入或选择课程
          </div>
        )}

        {activeCourseId && (
          <div className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl px-4 py-3 text-sm">
                {error}
              </div>
            )}

            {refreshFailed && (
              <div className="bg-amber-50 border border-amber-100 text-amber-700 rounded-xl px-4 py-3 text-sm">
                {refreshFailureMessage}
              </div>
            )}

            <section className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              {[
                ['KG 节点总数', overview.total],
                ['已练习节点', overview.practiced],
                ['待练习节点', overview.pending],
                ['未测评/默认通过', overview.defaultPass],
                ['最近评估时间', formatDate(effectsData?.generated_at)],
              ].map(([label, value]) => (
                <div key={label} className="bg-white/80 backdrop-blur-md rounded-xl p-4 shadow-sm border border-gray-100 min-h-24">
                  <div className="text-xs text-slate-400 mb-2">{label}</div>
                  <div className="text-2xl font-bold text-slate-800 break-words">{value}</div>
                </div>
              ))}
            </section>

            <section className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-8 bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100">
                <h3 className="font-h3 text-xl font-bold mb-3 flex items-center">
                  <Icon name="psychology" className="material-symbols-outlined mr-2 text-cyan-600"/>
                  学习效果总结
                </h3>
                {loading ? (
                  <p className="font-body-md text-slate-500 leading-relaxed">正在加载学习效果...</p>
                ) : effectsData?.summary_text ? (
                  <p className="font-body-md text-slate-600 leading-relaxed">{effectsData.summary_text}</p>
                ) : (
                  <p className="font-body-md text-slate-500 leading-relaxed">
                    暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
                  </p>
                )}
              </div>

              <div className="col-span-12 lg:col-span-4 bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100">
                <h3 className="font-h3 text-xl font-bold mb-4 flex items-center">
                  <Icon name="donut_large" className="material-symbols-outlined mr-2 text-cyan-600"/>
                  掌握度分布
                </h3>
                <div className="space-y-3">
                  {masteryDistribution.map(group => {
                    const width = overview.total ? `${Math.round((group.count / overview.total) * 100)}%` : '0%';
                    return (
                      <div key={group.key} className="space-y-1">
                        <div className="flex justify-between text-sm text-slate-600">
                          <span>{group.label}</span>
                          <span className="font-semibold">{group.count}</span>
                        </div>
                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className={`h-full ${group.color}`} style={{ width }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

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
                            {hasPracticeEvidence(row)
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
          </div>
        )}
      </main>
    </div>
  );
}
