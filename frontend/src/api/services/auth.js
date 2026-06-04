import apiClient from '../client';

export const authService = {
  getCurrentUser() {
    return apiClient.get('/users/me');
  },
  getCaptcha() {
    return apiClient.get('/auth/captcha');
  },
  login(data) {
    return apiClient.post('/auth/login', data);
  },
  register(data) {
    return apiClient.post('/auth/register', data);
  },
  logout: async () => {
    return apiClient.post('/auth/logout');
  },

  // 刷新 Token
  refreshToken: async (refreshToken) => {
    return apiClient.post('/auth/refresh', { refresh_token: refreshToken });
  },

  // 发送重置密码验证码
  sendResetPasswordCode: async (email) => {
    return apiClient.post('/auth/reset-password/code', { email });
  },

  // 重置密码
  resetPassword: async (email, code, newPassword) => {
    return apiClient.post('/auth/reset-password', { email, code, new_password: newPassword });
  }
};
