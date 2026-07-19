import { useEffect, useRef } from 'react';
import { learningActivityService } from '../api/services/learningActivity';
import { profileService } from '../api/services/profile';

export function useResourceStudyTracking({ courseId, resource, nodeContext = {} }) {
  const studyStartRef = useRef(null);

  useEffect(() => {
    if (!courseId || !resource?.id) return undefined;

    const activityContext = {
      course_id: courseId,
      resource_id: resource.id,
      node_id: nodeContext.id || nodeContext.node_id || null,
      node_name: nodeContext.name || nodeContext.node_name || resource.knowledge_point || null
    };
    const startStudy = () => {
      studyStartRef.current = Date.now();
    };
    const flushStudy = () => {
      const startedAt = studyStartRef.current;
      studyStartRef.current = null;
      if (!startedAt) return;
      const duration = Math.floor((Date.now() - startedAt) / 1000);
      if (duration < learningActivityService.minStudySeconds) return;
      learningActivityService.trackActivity({
        ...activityContext,
        activity_type: 'resource_study',
        duration_seconds: duration,
        metadata: { source: 'resource_detail' }
      }).then(result => {
        if (result) profileService.refreshProfile(courseId).catch(() => {});
      });
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') flushStudy();
      else if (!studyStartRef.current) startStudy();
    };

    startStudy();
    learningActivityService.trackActivity({
      ...activityContext,
      activity_type: 'resource_view',
      metadata: { source: 'resource_detail' }
    });
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      flushStudy();
    };
  }, [courseId, resource?.id, resource?.knowledge_point, nodeContext.id, nodeContext.name, nodeContext.node_id, nodeContext.node_name]);
}
