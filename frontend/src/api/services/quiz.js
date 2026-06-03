import apiClient from '../client';

export const quizService = {
  getQuestions(courseId, chapter) {
    return apiClient.get('/quiz/questions', { params: { course_id: courseId, chapter } });
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
