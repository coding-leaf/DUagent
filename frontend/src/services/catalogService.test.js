import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import apiClient from '../api/client';
import { catalogService } from './catalogService';

describe('catalogService', () => {
  let mock;

  beforeEach(() => {
    mock = new MockAdapter(apiClient);
  });

  afterEach(() => {
    mock.restore();
  });

  it('should fetch course catalogs', async () => {
    const params = { page: 1 };
    const responseData = { data: [] };
    mock.onGet('/admin/course-catalogs', { params }).reply(200, responseData);

    const result = await catalogService.getCourseCatalogs(params);
    expect(result).toEqual(responseData);
  });

  it('should create a course catalog', async () => {
    const data = { name: 'Test Catalog' };
    const responseData = { id: 1, name: 'Test Catalog' };
    mock.onPost('/admin/course-catalogs', data).reply(200, responseData);

    const result = await catalogService.createCourseCatalog(data);
    expect(result).toEqual(responseData);
  });

  it('should get course catalog knowledge status', async () => {
    const catalogId = '123';
    const responseData = { status: 'ready' };
    mock.onGet(`/admin/course-catalogs/${catalogId}/knowledge-status`).reply(200, responseData);

    const result = await catalogService.getCourseCatalogStatus(catalogId);
    expect(result).toEqual(responseData);
  });

  it('should create course catalog material', async () => {
    const catalogId = '123';
    const data = { title: 'New Material' };
    const responseData = { id: 'mat1', title: 'New Material' };
    mock.onPost(`/admin/course-catalogs/${catalogId}/materials`, data).reply(200, responseData);

    const result = await catalogService.createCourseCatalogMaterial(catalogId, data);
    expect(result).toEqual(responseData);
  });

  it('should get course catalog materials', async () => {
    const catalogId = '123';
    const responseData = { materials: [] };
    mock.onGet(`/admin/course-catalogs/${catalogId}/materials`).reply(200, responseData);

    const result = await catalogService.getCourseCatalogMaterials(catalogId);
    expect(result).toEqual(responseData);
  });

  it('should delete course catalog material', async () => {
    const catalogId = '123';
    const materialId = 'mat1';
    const responseData = { success: true };
    mock.onDelete(`/admin/course-catalogs/${catalogId}/materials/${materialId}`).reply(200, responseData);

    const result = await catalogService.deleteCourseCatalogMaterial(catalogId, materialId);
    expect(result).toEqual(responseData);
  });

  it('should upload course catalog material', async () => {
    const catalogId = '123';
    const file = new File(['dummy content'], 'test.txt', { type: 'text/plain' });
    const responseData = { message: 'Upload success' };
    
    mock.onPost(`/admin/course-catalogs/${catalogId}/materials/upload`).reply(200, responseData);

    const result = await catalogService.uploadCourseCatalogMaterial(catalogId, file);
    expect(result).toEqual(responseData);
  });

  it('should start course catalog ingestion', async () => {
    const catalogId = '123';
    const responseData = { task_id: 'task1' };
    mock.onPost(`/admin/course-catalogs/${catalogId}/ingestions`).reply(200, responseData);

    const result = await catalogService.startCourseCatalogIngestion(catalogId);
    expect(result).toEqual(responseData);
  });

  it('should get course catalog resources', async () => {
    const catalogId = '123';
    const params = { page: 1 };
    const responseData = { resources: [] };
    mock.onGet(`/admin/course-catalogs/${catalogId}/resources`, { params }).reply(200, responseData);

    const result = await catalogService.getCourseCatalogResources(catalogId, params);
    expect(result).toEqual(responseData);
  });

  it('should start course catalog resource generation', async () => {
    const catalogId = '123';
    const data = { chapter: '1' };
    const responseData = { task_id: 'task2' };
    mock.onPost(`/admin/course-catalogs/${catalogId}/resources/generations`, data).reply(200, responseData);

    const result = await catalogService.startCourseCatalogResourceGeneration(catalogId, data);
    expect(result).toEqual(responseData);
  });

  it('should get course catalog knowledge graph status', async () => {
    const catalogId = '123';
    const responseData = { status: 'generating' };
    mock.onGet(`/admin/course-catalogs/${catalogId}/knowledge-graphs`).reply(200, responseData);

    const result = await catalogService.getCourseCatalogKnowledgeGraphStatus(catalogId);
    expect(result).toEqual(responseData);
  });

  it('should start course catalog knowledge graph generation', async () => {
    const catalogId = '123';
    const data = { config: 'full' };
    const responseData = { task_id: 'task3' };
    mock.onPost(`/admin/course-catalogs/${catalogId}/knowledge-graphs/generations`, data).reply(200, responseData);

    const result = await catalogService.startCourseCatalogKnowledgeGraphGeneration(catalogId, data);
    expect(result).toEqual(responseData);
  });

  it('should delete a resource', async () => {
    const resourceId = 'res1';
    const responseData = { success: true };
    mock.onDelete(`/admin/resources/${resourceId}`).reply(200, responseData);

    const result = await catalogService.deleteResource(resourceId);
    expect(result).toEqual(responseData);
  });

  it('should start quiz generation', async () => {
    const catalogId = '123';
    const responseData = { task_id: 'task4' };
    mock.onPost(`/admin/course-catalogs/${catalogId}/quiz/generations`).reply(200, responseData);

    const result = await catalogService.startQuizGeneration(catalogId);
    expect(result).toEqual(responseData);
  });
});
