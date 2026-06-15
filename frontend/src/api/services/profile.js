import apiClient from '../client';

export const profileService = {
  getStudentProfile: async (courseId) => {
    return apiClient.get('/profile', { params: { course_id: courseId } });
  },

  refreshProfile: async (courseId) => {
    return apiClient.post('/profile/refresh', { course_id: courseId });
  },

  updateLearningGoal: async (courseId, goalType) => {
    return apiClient.post('/profile/learning-goal', { course_id: courseId, goal_type: goalType });
  },

  updateCustomInstruction: async (courseId, instruction) => {
    return apiClient.post('/profile/custom-instruction', { course_id: courseId, instruction });
  },

  getLearningEffects(courseId) {
    return apiClient.get('/evaluation', { params: { course_id: courseId } });
  }
};
