import apiClient from '../client';

export const personalizedResourcesService = {
  list(courseId, params = {}) {
    return apiClient.get('/personalized-resources', { params: { course_id: courseId, ...params } });
  },
  generate(data) {
    return apiClient.post('/personalized-resources/generate', data);
  },
};
