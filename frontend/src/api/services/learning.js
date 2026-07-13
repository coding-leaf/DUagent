import apiClient from '../client';

export const learningService = {
  getLearningPath(courseId) {
    return apiClient.get('/learning-path', { params: { course_id: courseId } });
  },
  getResources(params) {
    return apiClient.get('/resources', { params });
  },
  refreshEvaluation(courseId) {
    return apiClient.post('/evaluation/refresh', { course_id: courseId });
  },
  getResourceDetail(id) {
    return apiClient.get(`/resources/${id}`);
  },
  getNodeResources(nodeId, courseId) {
    return apiClient.get(`/learning-path/nodes/${nodeId}/resources`, {
      params: { course_id: courseId }
    });
  }
};
