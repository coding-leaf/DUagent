import apiClient from '../api/client';

export const catalogService = {
  /**
   * Get all course catalogs
   * @param {Object} params - Query parameters
   * @returns {Promise<Object>}
   */
  async getCourseCatalogs(params) {
    return await apiClient.get('/admin/course-catalogs', { params });
  },

  /**
   * Create a new course catalog
   * @param {Object} data - Catalog data
   * @returns {Promise<Object>}
   */
  async createCourseCatalog(data) {
    return await apiClient.post('/admin/course-catalogs', data);
  },

  /**
   * Get course catalog knowledge status
   * @param {string} catalogId
   * @returns {Promise<Object>}
   */
  async getCourseCatalogStatus(catalogId) {
    return await apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-status`);
  },

  /**
   * Create course catalog material
   * @param {string} catalogId
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  async createCourseCatalogMaterial(catalogId, data) {
    return await apiClient.post(`/admin/course-catalogs/${catalogId}/materials`, data);
  },

  /**
   * Get course catalog materials
   * @param {string} catalogId
   * @returns {Promise<Object>}
   */
  async getCourseCatalogMaterials(catalogId) {
    return await apiClient.get(`/admin/course-catalogs/${catalogId}/materials`);
  },

  /**
   * Delete a course catalog material
   * @param {string} catalogId
   * @param {string} materialId
   * @returns {Promise<Object>}
   */
  async deleteCourseCatalogMaterial(catalogId, materialId) {
    return await apiClient.delete(`/admin/course-catalogs/${catalogId}/materials/${materialId}`);
  },

  /**
   * Upload a course catalog material
   * @param {string} catalogId
   * @param {File} file
   * @returns {Promise<Object>}
   */
  async uploadCourseCatalogMaterial(catalogId, file) {
    const formData = new FormData();
    formData.append('file', file);
    return await apiClient.post(`/admin/course-catalogs/${catalogId}/materials/upload`, formData, {
      timeout: 60000,
    });
  },

  /**
   * Start course catalog ingestion
   * @param {string} catalogId
   * @returns {Promise<Object>}
   */
  async startCourseCatalogIngestion(catalogId) {
    return await apiClient.post(`/admin/course-catalogs/${catalogId}/ingestions`);
  },

  /**
   * Get course catalog generated resources
   * @param {string} catalogId
   * @param {Object} params
   * @returns {Promise<Object>}
   */
  async getCourseCatalogResources(catalogId, params) {
    return await apiClient.get(`/admin/course-catalogs/${catalogId}/resources`, { params });
  },

  /**
   * Start course catalog resource generation
   * @param {string} catalogId
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  async startCourseCatalogResourceGeneration(catalogId, data) {
    return await apiClient.post(`/admin/course-catalogs/${catalogId}/resources/generations`, data);
  },

  /**
   * Get course catalog knowledge graph status
   * @param {string} catalogId
   * @returns {Promise<Object>}
   */
  async getCourseCatalogKnowledgeGraphStatus(catalogId) {
    return await apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-graphs`);
  },

  /**
   * Start course catalog knowledge graph generation
   * @param {string} catalogId
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  async startCourseCatalogKnowledgeGraphGeneration(catalogId, data) {
    return await apiClient.post(`/admin/course-catalogs/${catalogId}/knowledge-graphs/generations`, data);
  },

  /**
   * Delete a generated resource
   * @param {string} resourceId
   * @returns {Promise<Object>}
   */
  async deleteResource(resourceId) {
    return await apiClient.delete(`/admin/resources/${resourceId}`);
  },

  /**
   * Start quiz generation
   * @param {string} catalogId
   * @returns {Promise<Object>}
   */
  async startQuizGeneration(catalogId) {
    return await apiClient.post(`/admin/course-catalogs/${catalogId}/quiz/generations`);
  }
};

export default catalogService;
