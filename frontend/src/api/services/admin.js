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

  getCourseCatalogs: async (params) => apiClient.get('/admin/course-catalogs', { params }),

  createCourseCatalog: async (data) => apiClient.post('/admin/course-catalogs', data),

  getCourseCatalogStatus: async (catalogId) => apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-status`),

  createCourseCatalogMaterial: async (catalogId, data) => apiClient.post(`/admin/course-catalogs/${catalogId}/materials`, data),

  getCourseCatalogMaterials: async (catalogId) => {
    return apiClient.get(`/admin/course-catalogs/${catalogId}/materials`);
  },

  deleteCourseCatalogMaterial: async (catalogId, materialId) => {
    return apiClient.delete(`/admin/course-catalogs/${catalogId}/materials/${materialId}`);
  },

  uploadCourseCatalogMaterial: async (catalogId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/admin/course-catalogs/${catalogId}/materials/upload`, formData, {
      timeout: 60000,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
  },

  startCourseCatalogIngestion: async (catalogId) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/ingestions`);
  },

  getCourseCatalogResources: async (catalogId, params) => {
    return apiClient.get(`/admin/course-catalogs/${catalogId}/resources`, { params });
  },

  startCourseCatalogResourceGeneration: async (catalogId, data) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/resources/generations`, data);
  },

  getCourseCatalogKnowledgeGraphStatus: async (catalogId) => {
    return apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-graphs`);
  },

  startCourseCatalogKnowledgeGraphGeneration: async (catalogId, data) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/knowledge-graphs/generations`, data);
  },

  deleteResource: async (resourceId) => {
    return apiClient.delete(`/admin/resources/${resourceId}`);
  }
};
