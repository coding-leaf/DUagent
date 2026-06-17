import apiClient from '../client';

export const catalogService = {
  getCourseCatalogs: (params) => apiClient.get('/admin/course-catalogs', { params }),

  createCourseCatalog: (data) => apiClient.post('/admin/course-catalogs', data),

  getCourseCatalogStatus: (catalogId) =>
    apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-status`),

  createCourseCatalogMaterial: (catalogId, data) =>
    apiClient.post(`/admin/course-catalogs/${catalogId}/materials`, data),

  getCourseCatalogMaterials: (catalogId) =>
    apiClient.get(`/admin/course-catalogs/${catalogId}/materials`),

  deleteCourseCatalogMaterial: (catalogId, materialId) =>
    apiClient.delete(`/admin/course-catalogs/${catalogId}/materials/${materialId}`),

  // multipart/form-data with extended timeout for large file uploads
  // async is needed here because we construct FormData before the call
  uploadCourseCatalogMaterial: async (catalogId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/admin/course-catalogs/${catalogId}/materials/upload`, formData, {
      timeout: 60000,
    });
  },

  startCourseCatalogIngestion: (catalogId) =>
    apiClient.post(`/admin/course-catalogs/${catalogId}/ingestions`),

  getCourseCatalogResources: (catalogId, params) =>
    apiClient.get(`/admin/course-catalogs/${catalogId}/resources`, { params }),

  startCourseCatalogResourceGeneration: (catalogId, data) =>
    apiClient.post(`/admin/course-catalogs/${catalogId}/resources/generations`, data),

  getCourseCatalogKnowledgeGraphStatus: (catalogId) =>
    apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-graphs`),

  startCourseCatalogKnowledgeGraphGeneration: (catalogId, data) =>
    apiClient.post(`/admin/course-catalogs/${catalogId}/knowledge-graphs/generations`, data),

  deleteResource: (resourceId) =>
    apiClient.delete(`/admin/resources/${resourceId}`),

  startQuizGeneration: (catalogId) =>
    apiClient.post(`/admin/course-catalogs/${catalogId}/quiz/generations`),
};
