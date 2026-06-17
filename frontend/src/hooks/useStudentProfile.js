import { useState } from 'react';
import useSWR from 'swr';
import { profileService } from '../api/services/profile';
import { taskService } from '../api/services/task';

const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200 && res.code !== 202) {
    throw new Error(res.message || '请求失败');
  }
  return res;
};

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
  useSWR(
    isPolling && refreshTask?.task_id ? ['profileTask', refreshTask.task_id] : null,
    () => fetcherWrapper(taskService.getTaskStatus(refreshTask.task_id)),
    {
      refreshInterval: (data) => {
        const status = data?.data?.status;
        return (status === 'completed' || status === 'failed' || status === 'partial') ? 0 : 2000;
      },
      onSuccess: (res) => {
        const status = res.data?.status || 'processing';
        setRefreshTask(prev => ({ ...prev, status, error_message: res.data?.error_message }));
        if (status === 'completed') {
          mutateProfile(); // Refresh profile when task completes
        }
      },
      onError: (err) => {
        setRefreshTask({ status: 'failed', error_message: err.message });
      }
    }
  );

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
