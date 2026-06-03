import apiClient from '../client';

export const profileService = {
  getStudentProfile: async () => {
    return apiClient.get('/profile/student');
  },

  // 修改个人信息
  updateProfile: async (data) => {
    return apiClient.put('/profile/student', data);
  },

  // 刷新用户画像 (触发 Agent 重新生成)
  refreshProfile: async () => {
    return apiClient.post('/profile/refresh');
  },

  getLearningEffects() {
    return apiClient.get('/evaluation/learning-effects');
  }
};
