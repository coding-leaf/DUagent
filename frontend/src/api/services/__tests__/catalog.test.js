import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

import apiClient from '../../client';
import { catalogService } from '../catalog';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('catalogService', () => {
  describe('getCourseCatalogs', () => {
    it('calls GET /admin/course-catalogs with params', async () => {
      apiClient.get.mockResolvedValue({ data: [] });
      const params = { page: 1, page_size: 10 };

      await catalogService.getCourseCatalogs(params);

      expect(apiClient.get).toHaveBeenCalledWith('/admin/course-catalogs', { params });
    });
  });

  describe('createCourseCatalog', () => {
    it('calls POST /admin/course-catalogs with data', async () => {
      const data = { name: 'Test Catalog' };
      apiClient.post.mockResolvedValue({ data });

      await catalogService.createCourseCatalog(data);

      expect(apiClient.post).toHaveBeenCalledWith('/admin/course-catalogs', data);
    });
  });

  describe('getCourseCatalogStatus', () => {
    it('calls GET /admin/course-catalogs/:id/knowledge-status', async () => {
      apiClient.get.mockResolvedValue({ data: {} });

      await catalogService.getCourseCatalogStatus('cat-1');

      expect(apiClient.get).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/knowledge-status');
    });
  });

  describe('createCourseCatalogMaterial', () => {
    it('calls POST /admin/course-catalogs/:id/materials with data', async () => {
      const data = { url: 'http://example.com/file.pdf' };
      apiClient.post.mockResolvedValue({ data });

      await catalogService.createCourseCatalogMaterial('cat-1', data);

      expect(apiClient.post).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/materials', data);
    });
  });

  describe('getCourseCatalogMaterials', () => {
    it('calls GET /admin/course-catalogs/:id/materials', async () => {
      apiClient.get.mockResolvedValue({ data: [] });

      await catalogService.getCourseCatalogMaterials('cat-1');

      expect(apiClient.get).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/materials');
    });
  });

  describe('deleteCourseCatalogMaterial', () => {
    it('calls DELETE with correct catalogId and materialId', async () => {
      apiClient.delete.mockResolvedValue({ data: {} });

      await catalogService.deleteCourseCatalogMaterial('cat-1', 'mat-42');

      expect(apiClient.delete).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/materials/mat-42');
    });
  });

  describe('uploadCourseCatalogMaterial', () => {
    it('posts FormData with 60s timeout and no explicit Content-Type header', async () => {
      apiClient.post.mockResolvedValue({ data: {} });
      const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });

      await catalogService.uploadCourseCatalogMaterial('cat-1', file);

      expect(apiClient.post).toHaveBeenCalledTimes(1);
      const [url, body, config] = apiClient.post.mock.calls[0];

      expect(url).toBe('/admin/course-catalogs/cat-1/materials/upload');
      expect(body).toBeInstanceOf(FormData);
      expect(body.get('file')).toBe(file);
      expect(config.timeout).toBe(60000);
      expect(config.headers).toBeUndefined();
    });
  });

  describe('startCourseCatalogIngestion', () => {
    it('calls POST /admin/course-catalogs/:id/ingestions', async () => {
      apiClient.post.mockResolvedValue({ data: {} });

      await catalogService.startCourseCatalogIngestion('cat-1');

      expect(apiClient.post).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/ingestions');
    });
  });

  describe('getCourseCatalogResources', () => {
    it('calls GET /admin/course-catalogs/:id/resources with params', async () => {
      apiClient.get.mockResolvedValue({ data: [] });
      const params = { page: 1, page_size: 50 };

      await catalogService.getCourseCatalogResources('cat-1', params);

      expect(apiClient.get).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/resources', { params });
    });
  });

  describe('startCourseCatalogResourceGeneration', () => {
    it('calls POST /admin/course-catalogs/:id/resources/generations with data', async () => {
      const data = { mode: 'auto' };
      apiClient.post.mockResolvedValue({ data: {} });

      await catalogService.startCourseCatalogResourceGeneration('cat-1', data);

      expect(apiClient.post).toHaveBeenCalledWith(
        '/admin/course-catalogs/cat-1/resources/generations',
        data
      );
    });
  });

  describe('getCourseCatalogKnowledgeGraphStatus', () => {
    it('calls GET /admin/course-catalogs/:id/knowledge-graphs', async () => {
      apiClient.get.mockResolvedValue({ data: {} });

      await catalogService.getCourseCatalogKnowledgeGraphStatus('cat-1');

      expect(apiClient.get).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/knowledge-graphs');
    });
  });

  describe('startCourseCatalogKnowledgeGraphGeneration', () => {
    it('calls POST /admin/course-catalogs/:id/knowledge-graphs/generations with data', async () => {
      const data = { rebuild: true };
      apiClient.post.mockResolvedValue({ data: {} });

      await catalogService.startCourseCatalogKnowledgeGraphGeneration('cat-1', data);

      expect(apiClient.post).toHaveBeenCalledWith(
        '/admin/course-catalogs/cat-1/knowledge-graphs/generations',
        data
      );
    });
  });

  describe('deleteResource', () => {
    it('calls DELETE /admin/resources/:id', async () => {
      apiClient.delete.mockResolvedValue({ data: {} });

      await catalogService.deleteResource('res-99');

      expect(apiClient.delete).toHaveBeenCalledWith('/admin/resources/res-99');
    });
  });

  describe('startQuizGeneration', () => {
    it('calls POST /admin/course-catalogs/:id/quiz/generations', async () => {
      apiClient.post.mockResolvedValue({ data: {} });

      await catalogService.startQuizGeneration('cat-1');

      expect(apiClient.post).toHaveBeenCalledWith('/admin/course-catalogs/cat-1/quiz/generations');
    });
  });
});
