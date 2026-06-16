import apiClient from '../client';

export const personalizedResourcesService = {
  list(courseId, params = {}) {
    return apiClient.get('/personalized-resources', { params: { course_id: courseId, ...params } });
  },
  generate(data) {
    // Agent 生成可能耗时 30-60s，单独设置长超时
    return apiClient.post('/personalized-resources/generate', data, { timeout: 90000 });
  },
};
