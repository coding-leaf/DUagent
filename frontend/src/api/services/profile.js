import apiClient from '../client';

export const profileService = {
  getStudentProfile: async (courseId) => {
    return apiClient.get('/profile', { params: { course_id: courseId } });
  },

  // 刷新用户画像 (触发 Agent 重新生成)
  refreshProfile: async (courseId) => {
    return apiClient.post('/profile/refresh', { course_id: courseId });
  },

  updateProfileByDialogue: async (courseId, message) => {
    return apiClient.post('/profile/dialogue-update', { course_id: courseId, message });
  },

  getLearningEffects(courseId) {
    return apiClient.get('/evaluation', { params: { course_id: courseId } });
  }
};
