import { useMemo } from 'react';
import useSWR from 'swr';
import { learningService } from '../api/services/learning';
import { fetcherWrapper } from '../utils/fetcher';

export function useRecommendedResources(activeCourseId, messages) {
  const { data: resourcesRes, error, isLoading } = useSWR(
    activeCourseId ? ['recommendedResources', activeCourseId] : null,
    () => fetcherWrapper(learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 100 }))
  );

  const resources = useMemo(() => {
    const resourcesData = resourcesRes?.data?.resources || resourcesRes?.data;
    return Array.isArray(resourcesData) ? resourcesData : [];
  }, [resourcesRes]);

  const activeKPs = useMemo(() => {
    if (!messages || !Array.isArray(messages)) return [];
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.knowledge_points && msg.knowledge_points.length > 0) {
        return msg.knowledge_points;
      }
    }
    return [];
  }, [messages]);

  const recommendedResources = useMemo(() => {
    return resources.filter(res => {
      if (activeKPs.length === 0) return true;
      return activeKPs.some(kp => 
        res.knowledge_point?.toLowerCase().includes(kp.toLowerCase()) ||
        res.title?.toLowerCase().includes(kp.toLowerCase())
      );
    });
  }, [resources, activeKPs]);

  return {
    recommendedResources,
    error,
    isLoading
  };
}
