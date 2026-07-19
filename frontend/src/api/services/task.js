import apiClient from '../client';

export const taskService = {
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}`);
  }
};
