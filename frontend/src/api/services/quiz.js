import apiClient from '../client';

export const quizService = {
  getQuestions(courseId, nodeId, extraParams = {}) {
    const params = { course_id: courseId, ...extraParams };
    if (nodeId) params.node_id = nodeId;
    return apiClient.get('/quiz/questions', { params });
  },
  submitQuiz(data) {
    return apiClient.post('/quiz/submit', data);
  },
  getResult(courseId) {
    return apiClient.get('/quiz/result', { params: { course_id: courseId } });
  },
  getHistory(params) {
    return apiClient.get('/quiz/history', { params });
  }
};
