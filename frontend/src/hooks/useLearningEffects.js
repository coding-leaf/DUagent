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

  const refreshFailed = !!(refreshTask && terminalTaskStates.has(refreshTask.status) && refreshTask.status !== 'completed');
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
