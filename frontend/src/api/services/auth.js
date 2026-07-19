import apiClient from '../client';

export const authService = {
  getCurrentUser() {
    return apiClient.get('/users/me');
  },
  updateMyInfo(data) {
    return apiClient.put('/users/me', data);
  },
  getCaptcha() {
    return apiClient.get('/auth/captcha');
  },
  login(data) {
    return apiClient.post('/auth/login', data);
  },
  register(data) {
    return apiClient.post('/auth/register', data);
  }
};
