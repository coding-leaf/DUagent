import axios from 'axios';
import { toast } from 'sonner';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    if (error.response) {
      const { status } = error.response;
      if (status === 401) {
        console.error('Authentication failed, token expired.');
        localStorage.removeItem('access_token');
        // No toast needed, redirect is explicit enough
        window.location.href = '/login';
      } else if (status === 403) {
        toast.error('权限不足');
      } else if (status >= 500) {
        toast.error('服务器错误，请稍后重试');
      }
      // Other 4xx errors are passed down to be handled by component catch blocks
      // to avoid toast bombing alongside inline error UI.
    } else {
      console.error('Network Error:', error.message);
      toast.error('网络错误，请检查您的连接');
    }
    return Promise.reject(error);
  }
);

export default apiClient;
