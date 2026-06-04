import apiClient from '../client';

export const learningService = {
  getLearningPath(courseId) {
    return apiClient.get('/learning-path', { params: { course_id: courseId } });
  },
  refreshLearningPath(courseId) {
    return apiClient.post('/learning-path/refresh', { course_id: courseId });
  },
  getResources(params) {
    return apiClient.get('/resources', { params });
  },
  refreshEvaluation() {
    return apiClient.post('/evaluation/refresh');
  },
  triggerResourceGeneration(params) {
    return apiClient.post('/resources/generate', params);
  },
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}`);
  }
};
