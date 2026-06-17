import { useState, useEffect } from 'react';
import useSWR from 'swr';
import { profileService } from '../api/services/profile';
import { taskService } from '../api/services/task';
import { fetcherWrapper } from '../utils/fetcher';

export function useStudentProfile(activeCourseId) {
  const [refreshTask, setRefreshTask] = useState(null);
  
  // Profile Fetching
  const { data: profileRes, error: profileError, mutate: mutateProfile, isLoading: profileLoading } = useSWR(
    activeCourseId ? ['studentProfile', activeCourseId] : null,
    () => fetcherWrapper(profileService.getStudentProfile(activeCourseId))
  );

  const profileData = profileRes?.data || null;

  // Task Polling with SWR (Only polls when refreshTask is active and processing)
  const isPolling = refreshTask?.status === 'processing';
  const { data: taskRes, error: taskError } = useSWR(
    isPolling && refreshTask?.task_id ? ['profileTask', refreshTask.task_id] : null,
    () => fetcherWrapper(taskService.getTaskStatus(refreshTask.task_id)),
    {
      refreshInterval: (data) => {
        const status = data?.data?.status;
        return (status === 'completed' || status === 'failed' || status === 'partial') ? 0 : 2000;
      }
    }
  );

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (taskRes?.data) {
      const status = taskRes.data.status || 'processing';
      setRefreshTask(prev => {
        // Prevent unnecessary state updates if status hasn't changed to completion/failure
        if (prev?.status === status && !taskRes.data.error_message) return prev;
        return { ...prev, status, error_message: taskRes.data.error_message };
      });
      if (status === 'completed') {
        mutateProfile(); // Refresh profile when task completes
      }
    } else if (taskError) {
      setRefreshTask(prev => {
        if (prev?.status === 'failed') return prev;
        return { status: 'failed', error_message: taskError.message };
      });
    }
  }, [taskRes, taskError, mutateProfile]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleProfileRefresh = async () => {
    if (!activeCourseId || isPolling) return;
    try {
      setRefreshTask({ status: 'processing' });
      const res = await profileService.refreshProfile(activeCourseId);
      if (res.code === 202 && res.data?.task_id) {
        setRefreshTask({ task_id: res.data.task_id, status: 'processing' });
      } else {
        setRefreshTask({ status: 'failed', error_message: res.message || '启动失败' });
      }
    } catch (err) {
      setRefreshTask({ status: 'failed', error_message: err.response?.data?.detail?.message || '启动失败' });
    }
  };

  return {
    profileData,
    profileLoading,
    profileError: profileError ? '加载失败，请重试' : null,
    mutateProfile,
    refreshTask,
    isPolling,
    handleProfileRefresh,
    setRefreshTask
  };
}
