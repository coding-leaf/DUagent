# LearningEffects Frontend Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the `LearningEffects.jsx` page by extracting logic into a `useLearningEffects` custom hook with SWR and task polling, and split UI cards into presentational components.

**Architecture:** Container/Presentational Pattern + Custom Hook Pattern. The custom hook encapsulates SWR data fetching, dual SWR background task status polling, and derived states calculation, exposing pure interfaces. The components are stateless views rendering pure props.

**Tech Stack:** React, SWR, Tailwind CSS, Vitest.

---

## File Structure

- Create: `src/hooks/useLearningEffects.js` (State and polling logic hook)
- Create: `src/hooks/__tests__/useLearningEffects.test.js` (Unit test for hook)
- Create: `src/components/effects/EffectsOverviewCards.jsx` (Overview grid metrics card)
- Create: `src/components/effects/EffectsSummaryCard.jsx` (AI Summary card)
- Create: `src/components/effects/MasteryDistributionCard.jsx` (Progress bar charts card)
- Create: `src/components/effects/KnowledgeProgressTable.jsx` (Knowledge point status data table)
- Modify: `src/pages/LearningEffects.jsx` (Simplifies page as clean visual assembler)

---

## Tasks

### Task 1: Create Custom Hook and Unit Test

**Files:**
- Create: `src/hooks/useLearningEffects.js`
- Create: `src/hooks/__tests__/useLearningEffects.test.js`

- [ ] **Step 1: Write the failing unit test**

Create `src/hooks/__tests__/useLearningEffects.test.js`. It imports `mutate` from `swr` to clear SWR cache in `beforeEach`, mocks the services, and uses `vi.useFakeTimers()` to test SWR polling and revalidation behaviors:

```javascript
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useLearningEffects } from '../useLearningEffects';
import { profileService } from '../../api/services/profile';
import { learningService } from '../../api/services/learning';
import { taskService } from '../../api/services/task';
import { mutate } from 'swr';

vi.mock('../../api/services/profile', () => ({
  profileService: {
    getLearningEffects: vi.fn()
  }
}));

vi.mock('../../api/services/learning', () => ({
  learningService: {
    refreshEvaluation: vi.fn()
  }
}));

vi.mock('../../api/services/task', () => ({
  taskService: {
    getTaskStatus: vi.fn()
  }
}));

describe('useLearningEffects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    // Clear SWR cache to avoid test pollution
    mutate(() => true, undefined, { revalidate: false });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not fetch when activeCourseId is missing', () => {
    const { result } = renderHook(() => useLearningEffects(null));
    expect(profileService.getLearningEffects).not.toHaveBeenCalled();
    expect(result.current.effectsData).toBeNull();
  });

  it('fetches and returns derived states correctly', async () => {
    const mockData = {
      generated_at: '2026-06-18T00:00:00Z',
      summary_text: 'Summary of learning',
      node_progress: [
        { node_id: 'n1', node_name: 'Node 1', assessment_state: 'mastered', mastery_label: 'A', question_count: 5 },
        { node_id: 'n2', node_name: 'Node 2', assessment_state: 'pending_practice', question_count: 3 }
      ]
    };
    profileService.getLearningEffects.mockResolvedValue({ code: 200, data: mockData });
    const { result } = renderHook(() => useLearningEffects('c123'));
    
    await waitFor(() => {
      expect(result.current.effectsData).toEqual(mockData);
      expect(result.current.overview.total).toBe(2);
      expect(result.current.overview.practiced).toBe(1);
      expect(result.current.overview.pending).toBe(1);
    });
  });

  it('triggers refresh and processes SWR polling and revalidation on completion', async () => {
    const mockData = { node_progress: [] };
    profileService.getLearningEffects.mockResolvedValue({ code: 200, data: mockData });
    learningService.refreshEvaluation.mockResolvedValue({ code: 202, data: { task_id: 'task999' } });
    
    // Simulate task status transition: first processing, then completed
    let taskCallCount = 0;
    taskService.getTaskStatus.mockImplementation(async () => {
      taskCallCount++;
      if (taskCallCount === 1) {
        return { code: 200, data: { status: 'processing', progress: 50 } };
      }
      return { code: 200, data: { status: 'completed', progress: 100 } };
    });

    const { result } = renderHook(() => useLearningEffects('c123'));
    
    // Trigger refresh
    await act(async () => {
      await result.current.handleRefresh();
    });

    expect(learningService.refreshEvaluation).toHaveBeenCalledWith('c123');
    expect(result.current.refreshTask?.task_id).toBe('task999');
    expect(result.current.isPolling).toBe(true);

    // Advance timer to trigger first SWR poll (returns processing)
    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    expect(taskService.getTaskStatus).toHaveBeenCalledTimes(1);
    expect(result.current.refreshTask?.status).toBe('processing');
    expect(result.current.isPolling).toBe(true);

    // Reset profileService mock call history to check for mutator refetch
    profileService.getLearningEffects.mockClear();

    // Advance timer to trigger second SWR poll (returns completed)
    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(taskService.getTaskStatus).toHaveBeenCalledTimes(2);
      expect(result.current.refreshTask?.status).toBe('completed');
      expect(result.current.isPolling).toBe(false);
      // Verify main mutator was triggered to refetch effects data
      expect(profileService.getLearningEffects).toHaveBeenCalled();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/hooks/__tests__/useLearningEffects.test.js`
Expected: Test fails due to missing Hook file `useLearningEffects.js`.

- [ ] **Step 3: Write Hook implementation**

Create `src/hooks/useLearningEffects.js`:

```javascript
import { useState, useEffect, useMemo } from 'react';
import useSWR from 'swr';
import { profileService } from '../api/services/profile';
import { learningService } from '../api/services/learning';
import { taskService } from '../api/services/task';
import { fetcherWrapper } from '../utils/fetcher';

const terminalTaskStates = new Set(['completed', 'failed', 'partial']);

function normalizeRows(data) {
  if (Array.isArray(data?.node_progress)) return data.node_progress;
  if (Array.isArray(data?.progress_table?.rows)) {
    return data.progress_table.rows.filter(row => row?.node_id && row?.node_name);
  }
  return [];
}

function hasPracticeEvidence(row) {
  return Number(row.attempt_count || 0) > 0
    || ['scored', 'mastered', 'weak'].includes(row.assessment_state);
}

export function useLearningEffects(activeCourseId) {
  const [refreshTask, setRefreshTask] = useState(null);

  // Fetch learning effects data
  const { data: effectsRes, error: effectsError, mutate: mutateEffects, isLoading: effectsLoading } = useSWR(
    activeCourseId ? ['learningEffects', activeCourseId] : null,
    () => fetcherWrapper(profileService.getLearningEffects(activeCourseId))
  );

  const effectsData = effectsRes?.data || null;

  // Derived states: node progress rows, overview metrics, and mastery breakdown
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

  // Task status polling with SWR
  const isPolling = refreshTask?.status === 'processing';
  const { data: taskRes, error: taskError } = useSWR(
    isPolling && refreshTask?.task_id ? ['learningEffectsTask', refreshTask.task_id] : null,
    () => fetcherWrapper(taskService.getTaskStatus(refreshTask.task_id)),
    {
      refreshInterval: (data) => {
        const status = data?.data?.status;
        return (status && terminalTaskStates.has(status)) ? 0 : 1500;
      }
    }
  );

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (taskRes?.data) {
      const status = taskRes.data.status || 'processing';
      const progress = taskRes.data.progress ?? 0;
      setRefreshTask(prev => {
        if (prev?.status === status && !taskRes.data.error_message && prev?.progress === progress) return prev;
        return { 
          ...prev, 
          status, 
          progress,
          error_code: taskRes.data.error_code,
          error_message: taskRes.data.error_message 
        };
      });
      if (status === 'completed') {
        mutateEffects();
      }
    } else if (taskError) {
      setRefreshTask(prev => {
        if (prev?.status === 'failed') return prev;
        return { status: 'failed', error_message: taskError.message };
      });
    }
  }, [taskRes, taskError, mutateEffects]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleRefresh = async () => {
    if (!activeCourseId || isPolling) return;
    try {
      setRefreshTask({ status: 'processing', progress: 0 });
      const res = await learningService.refreshEvaluation(activeCourseId);
      if (res.code === 202 && res.data?.task_id) {
        setRefreshTask({ task_id: res.data.task_id, status: 'processing', progress: 0 });
      } else {
        setRefreshTask({ status: 'failed', error_message: res.message || '重新评估启动失败' });
      }
    } catch (err) {
      const errorMsg = err.response?.data?.detail?.message || '重新评估启动失败，请稍后重试';
      setRefreshTask({ status: 'failed', error_message: errorMsg });
    }
  };

  const refreshFailed = refreshTask && terminalTaskStates.has(refreshTask.status) && refreshTask.status !== 'completed';
  const refreshFailureMessage = refreshTask?.error_message
    || (refreshTask?.error_code ? `错误码：${refreshTask.error_code}` : '')
    || '重新评估未完整完成，当前页面保留最近一次可用评估。';

  return {
    effectsData,
    effectsLoading,
    effectsError: effectsError ? '加载失败，请重试' : null,
    mutateEffects,
    refreshTask,
    isPolling,
    refreshFailed,
    refreshFailureMessage,
    overview,
    masteryDistribution,
    nodeRows,
    handleRefresh,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/hooks/__tests__/useLearningEffects.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useLearningEffects.js src/hooks/__tests__/useLearningEffects.test.js
git commit -m "feat(effects): create useLearningEffects custom hook with SWR polling and unit tests"
```

---

### Task 2: Create Presentational Sub-components

**Files:**
- Create: `src/components/effects/EffectsOverviewCards.jsx`
- Create: `src/components/effects/EffectsSummaryCard.jsx`
- Create: `src/components/effects/MasteryDistributionCard.jsx`
- Create: `src/components/effects/KnowledgeProgressTable.jsx`

- [ ] **Step 1: Implement EffectsOverviewCards**

Create `src/components/effects/EffectsOverviewCards.jsx` (removed unused `Icon` import to pass lint rules):

```jsx
export default function EffectsOverviewCards({ overview, generatedAt }) {
  const formatDate = (value) => {
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
  };

  const cards = [
    ['KG 节点总数', overview.total],
    ['已练习节点', overview.practiced],
    ['待练习节点', overview.pending],
    ['未测评/默认通过', overview.defaultPass],
    ['最近评估时间', formatDate(generatedAt)],
  ];

  return (
    <section className="grid grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map(([label, value]) => (
        <div key={label} className="bg-white/80 backdrop-blur-md rounded-xl p-4 shadow-sm border border-gray-100 min-h-24">
          <div className="text-xs text-slate-400 mb-2">{label}</div>
          <div className="text-2xl font-bold text-slate-800 break-words">{value}</div>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 2: Implement EffectsSummaryCard**

Create `src/components/effects/EffectsSummaryCard.jsx`:

```jsx
import Icon from '../Icon';

export default function EffectsSummaryCard({ summaryText, loading }) {
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
      <h3 className="font-h3 text-xl font-bold mb-3 flex items-center">
        <Icon name="psychology" className="material-symbols-outlined mr-2 text-cyan-600"/>
        学习效果总结
      </h3>
      {loading ? (
        <p className="font-body-md text-slate-500 leading-relaxed">正在加载学习效果...</p>
      ) : summaryText ? (
        <p className="font-body-md text-slate-600 leading-relaxed">{summaryText}</p>
      ) : (
        <p className="font-body-md text-slate-500 leading-relaxed">
          暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Implement MasteryDistributionCard**

Create `src/components/effects/MasteryDistributionCard.jsx`:

```jsx
import Icon from '../Icon';

export default function MasteryDistributionCard({ masteryDistribution, totalNodes }) {
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
      <h3 className="font-h3 text-xl font-bold mb-4 flex items-center">
        <Icon name="donut_large" className="material-symbols-outlined mr-2 text-cyan-600"/>
        掌握度分布
      </h3>
      <div className="space-y-3 flex-1 flex flex-col justify-between">
        {masteryDistribution.map(group => {
          const width = totalNodes ? `${Math.round((group.count / totalNodes) * 100)}%` : '0%';
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
  );
}
```

- [ ] **Step 4: Implement KnowledgeProgressTable**

Create `src/components/effects/KnowledgeProgressTable.jsx` (removed `navigate` prop, using direct `useNavigate` for routing within component):

```jsx
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
  );
}
```

- [ ] **Step 5: Verify components compile correctly**

Run: `npm run build`
Expected: Success with no errors.

- [ ] **Step 6: Commit**

```bash
git add src/components/effects/EffectsOverviewCards.jsx src/components/effects/EffectsSummaryCard.jsx src/components/effects/MasteryDistributionCard.jsx src/components/effects/KnowledgeProgressTable.jsx
git commit -m "feat(effects): extract display components and clean navigate prop and icon import"
```

---

### Task 3: Simplify Page and Connect Hook

**Files:**
- Modify: `src/pages/LearningEffects.jsx`

- [ ] **Step 1: Simplify LearningEffects container**

Replace all existing content in `src/pages/LearningEffects.jsx` to consume `useLearningEffects` custom hook and output the modular subcomponents (no `navigate` prop passed to `<KnowledgeProgressTable>`):

```jsx
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import Icon from '../components/Icon';
import { useLearningEffects } from '../hooks/useLearningEffects';
import EffectsOverviewCards from '../components/effects/EffectsOverviewCards';
import EffectsSummaryCard from '../components/effects/EffectsSummaryCard';
import MasteryDistributionCard from '../components/effects/MasteryDistributionCard';
import KnowledgeProgressTable from '../components/effects/KnowledgeProgressTable';

export default function LearningEffects() {
  const { activeCourseId } = useCourse();

  const {
    effectsData,
    effectsLoading,
    effectsError,
    refreshTask,
    isPolling: refreshInProgress,
    refreshFailed,
    refreshFailureMessage,
    overview,
    masteryDistribution,
    nodeRows,
    handleRefresh,
  } = useLearningEffects(activeCourseId);

  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen">
      <Navbar />

      <main className="pt-24 pb-12 px-6 max-w-[1280px] mx-auto min-h-screen">
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
            {effectsError && (
              <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl px-4 py-3 text-sm">
                {effectsError}
              </div>
            )}

            {refreshFailed && (
              <div className="bg-amber-50 border border-amber-100 text-amber-700 rounded-xl px-4 py-3 text-sm">
                {refreshFailureMessage}
              </div>
            )}

            <EffectsOverviewCards
              overview={overview}
              generatedAt={effectsData?.generated_at}
            />

            <section className="grid grid-cols-12 gap-6">
              <div className="col-span-12 lg:col-span-8">
                <EffectsSummaryCard
                  summaryText={effectsData?.summary_text}
                  loading={effectsLoading}
                />
              </div>

              <div className="col-span-12 lg:col-span-4">
                <MasteryDistributionCard
                  masteryDistribution={masteryDistribution}
                  totalNodes={overview.total}
                />
              </div>
            </section>

            <KnowledgeProgressTable
              nodeRows={nodeRows}
              activeCourseId={activeCourseId}
            />
          </div>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Run linters**

Run: `npm run lint`
Expected: 0 errors/warnings.

- [ ] **Step 3: Run unit tests**

Run: `npm run test:unit`
Expected: All tests pass.

- [ ] **Step 4: Run production build**

Run: `npm run build`
Expected: Build successfully completes.

- [ ] **Step 5: Commit changes**

```bash
git add src/pages/LearningEffects.jsx
git commit -m "refactor(effects): simplify LearningEffects container by wiring custom hook and subcomponents"
```
