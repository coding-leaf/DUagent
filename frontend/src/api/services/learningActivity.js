import apiClient from '../client';

const MIN_STUDY_SECONDS = 5;

export const learningActivityService = {
  async trackActivity(payload) {
    try {
      return await apiClient.post('/learning-activities', {
        occurred_at: new Date().toISOString(),
        ...payload
      });
    } catch (error) {
      console.warn('Learning activity tracking failed:', error);
      return null;
    }
  },
  minStudySeconds: MIN_STUDY_SECONDS
};
