import apiClient from '../client';

export const adminService = {
  // 获取全量用户列表
  getUsers: async (params) => {
    return apiClient.get('/admin/users', { params });
  },

  // 修改指定用户信息及权限
  updateUser: async (userId, data) => {
    return apiClient.put(`/admin/users/${userId}`, data);
  },

  // 移除用户（软删除/停用）
  removeUser: async (userId) => {
    return apiClient.delete(`/admin/users/${userId}`);
  },

  // 拉取核心调度器与子智能体的运行日志
  getAgentLogs: async (params) => {
    return apiClient.get('/admin/logs/agent', { params });
  },

  // 拉取系统基础日志
  getSystemLogs: async (params) => {
    return apiClient.get('/admin/logs/operations', { params });
  },

  getRegistrationCodes: async (role) => {
    return apiClient.get('/admin/registration-codes', { params: role ? { role } : undefined });
  },

  createRegistrationCode: async (role) => {
    return apiClient.post('/admin/registration-codes', { role });
  },

  revokeRegistrationCode: async (codeId) => {
    return apiClient.delete(`/admin/registration-codes/${codeId}`);
  },
};
