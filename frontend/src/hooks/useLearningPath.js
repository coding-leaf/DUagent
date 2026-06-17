import { useEffect, useRef } from 'react';
import useSWR from 'swr';
import { learningService } from '../api/services/learning';
import { learningActivityService } from '../api/services/learningActivity';

const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200 && res.code !== 202) {
    throw new Error(res.message || '请求失败');
  }
  return res;
};

export function useLearningPath(activeCourseId, selectedNodeId, setSelectedNodeId) {
  const initialSelectionSkippedRef = useRef(false);

  // 1. Fetch Learning Path
  const { data: pathRes, error: pathError, isLoading: pathLoading } = useSWR(
    activeCourseId ? ['learningPath', activeCourseId] : null,
    () => fetcherWrapper(learningService.getLearningPath(activeCourseId))
  );

  const learningPath = pathRes?.data || null;

  // Default selected node (after learningPath loads)
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!learningPath?.nodes?.length) return;
    if (selectedNodeId) return; // Only auto-select if nothing is selected

    const cpId = learningPath.current_position?.node_id;
    if (cpId) { setSelectedNodeId(cpId); return; }
    
    const ip = learningPath.nodes.find(n => n.status === 'in_progress');
    if (ip) { setSelectedNodeId(ip.id); return; }
    
    const rec = learningPath.nodes.find(n => n.status === 'recommended');
    if (rec) { setSelectedNodeId(rec.id); return; }
    
    const first = learningPath.nodes.find(n => n.status !== 'pending');
    if (first) { setSelectedNodeId(first.id); return; }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [learningPath, selectedNodeId, setSelectedNodeId]);

  // 2. Fetch Node Resources
  const { data: resourcesRes, error: resourcesError, isLoading: resourcesLoading } = useSWR(
    (activeCourseId && selectedNodeId) ? ['nodeResources', activeCourseId, selectedNodeId] : null,
    () => fetcherWrapper(learningService.getNodeResources(selectedNodeId, activeCourseId))
  );

  const nodeResources = resourcesRes?.data || null;

  // 3. Track Activity
  useEffect(() => {
    if (!activeCourseId || !selectedNodeId || !learningPath?.nodes?.length) return;
    const selectedNode = learningPath.nodes.find((node) => node.id === selectedNodeId);
    if (!selectedNode) return;
    
    if (!initialSelectionSkippedRef.current) {
      initialSelectionSkippedRef.current = true;
      return;
    }
    
    learningActivityService.trackActivity({
      course_id: activeCourseId,
      activity_type: 'node_view',
      node_id: selectedNode.id,
      node_name: selectedNode.name,
      metadata: { source: 'learning_path' }
    });
  }, [activeCourseId, learningPath, selectedNodeId]);

  return {
    learningPath,
    pathLoading,
    pathError,
    nodeResources,
    resourcesLoading,
    resourcesError
  };
}
