import React from 'react';
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SWRConfig, useSWRConfig } from 'swr';
import { useCatalog } from '../useCatalog';
import { catalogService } from '../../api/services/catalog';
import { taskService } from '../../api/services/task';

vi.mock('../../api/services/catalog', () => ({
  catalogService: {
    getCourseCatalogMaterials: vi.fn(),
    getCourseCatalogStatus: vi.fn(),
    getCourseCatalogResources: vi.fn(),
    getCourseCatalogKnowledgeGraphStatus: vi.fn(),
    uploadCourseCatalogMaterial: vi.fn(),
    startCourseCatalogIngestion: vi.fn(),
    startCourseCatalogResourceGeneration: vi.fn(),
    startCourseCatalogKnowledgeGraphGeneration: vi.fn(),
    startQuizGeneration: vi.fn(),
    deleteCourseCatalogMaterial: vi.fn(),
    deleteResource: vi.fn()
  }
}));

vi.mock('../../api/services/task', () => ({
  taskService: {
    getTaskStatus: vi.fn()
  }
}));

let testMutate;
const Wrapper = ({ children }) => {
  const { mutate } = useSWRConfig();
  React.useEffect(() => {
    testMutate = mutate;
  }, [mutate]);
  return children;
};

const createWrapper = () => {
  return ({ children }) => React.createElement(
    SWRConfig,
    { value: { provider: () => new Map(), dedupingInterval: 0 } },
    React.createElement(Wrapper, null, children)
  );
};

describe('useCatalog', () => {
  const mockCatalog = { id: 'c123', name: 'Test Catalog' };
  const mockOnChanged = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnChanged.mockReset();
  });

  it('does not fetch when open is false or catalog is null', () => {
    renderHook(() => useCatalog({ catalog: null, open: false, onChanged: mockOnChanged }), {
      wrapper: createWrapper()
    });
    expect(catalogService.getCourseCatalogMaterials).not.toHaveBeenCalled();
    expect(catalogService.getCourseCatalogStatus).not.toHaveBeenCalled();
    expect(catalogService.getCourseCatalogResources).not.toHaveBeenCalled();
    expect(catalogService.getCourseCatalogKnowledgeGraphStatus).not.toHaveBeenCalled();
  });

  it('fetches and returns materials, status, resources, and kgStatus when open is true', async () => {
    const mockMaterials = [{ id: 'm1', name: 'Material 1', status: 'uploaded' }];
    const mockStatus = { status: 'ready', material_count: 1, pending_material_count: 0 };
    const mockResources = [{ id: 'r1', title: 'Resource 1' }];
    const mockKgStatus = { active_graph: true };

    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: mockMaterials } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: mockStatus });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: mockResources } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: mockKgStatus });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.materials).toEqual(mockMaterials);
      expect(result.current.knowledgeStatus).toEqual(mockStatus);
      expect(result.current.resources).toEqual(mockResources);
      expect(result.current.knowledgeGraphStatus).toEqual(mockKgStatus);
      expect(result.current.loading).toBe(false);
    });
  });

  it('handles material upload flow correctly', async () => {
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: [] } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: {} });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: [] } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: {} });
    catalogService.uploadCourseCatalogMaterial.mockResolvedValue({ message: 'Upload success' });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    const file = new File(['dummy content'], 'test.pdf', { type: 'application/pdf' });
    const event = { target: { files: [file], value: 'test.pdf' } };

    await act(async () => {
      await result.current.handleUpload(event);
    });

    expect(catalogService.uploadCourseCatalogMaterial).toHaveBeenCalledWith('c123', file);
    expect(result.current.uploadQueue[0].status).toBe('uploaded');
    expect(result.current.uploading).toBe(false);
    expect(mockOnChanged).toHaveBeenCalled();
  });

  it('handles start ingestion and task polling transitions', async () => {
    // Return a material with status 'uploaded' to ensure startDisabled is false
    const mockMaterials = [{ id: 'm1', name: 'Material 1', status: 'uploaded' }];
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: mockMaterials } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: { material_count: 1 } });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: [] } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: {} });
    
    catalogService.startCourseCatalogIngestion.mockResolvedValue({ data: { task_id: 'task-ingest-1', status: 'processing' } });
    
    // Initially processing
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-ingest-1', status: 'processing', progress: 50 } });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.materials).toEqual(mockMaterials);
      expect(result.current.startDisabled).toBe(false);
    });

    await act(async () => {
      await result.current.handleStartIngestion();
    });

    expect(catalogService.startCourseCatalogIngestion).toHaveBeenCalledWith('c123');
    
    await waitFor(() => {
      expect(result.current.ingesting).toBe(true);
      expect(result.current.activeTask.task_id).toBe('task-ingest-1');
      expect(result.current.activeTask.status).toBe('processing');
    });

    // Mock task complete
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-ingest-1', status: 'completed', progress: 100 } });

    await act(async () => {
      await testMutate(['taskStatus/ingestion', 'task-ingest-1']);
    });

    await waitFor(() => {
      expect(result.current.ingesting).toBe(false);
      expect(result.current.activeTask.status).toBe('completed');
      expect(mockOnChanged).toHaveBeenCalled();
    });
  });

  it('handles start resource generation and task polling transitions', async () => {
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: [] } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: { status: 'ready', knowledge_status: 'ready', chunk_count: 5 } });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: [] } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: { active_graph: true } });
    
    catalogService.startCourseCatalogResourceGeneration.mockResolvedValue({ data: { task_id: 'task-gen-1', status: 'processing' } });
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-gen-1', status: 'processing', progress: 30 } });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.generationDisabled).toBe(true); // generationForm.resource_types is empty by default
    });

    await act(async () => {
      result.current.handleGenerationFieldChange('chapter', 'Chapter 1');
      result.current.handleGenerationTypeToggle('quiz');
    });

    await waitFor(() => {
      expect(result.current.generationDisabled).toBe(false);
    });

    await act(async () => {
      await result.current.handleStartGeneration();
    });

    expect(catalogService.startCourseCatalogResourceGeneration).toHaveBeenCalledWith('c123', {
      chapter: 'Chapter 1',
      knowledge_point: '',
      resource_types: ['quiz']
    });

    await waitFor(() => {
      expect(result.current.generating).toBe(true);
      expect(result.current.generationTask.task_id).toBe('task-gen-1');
      expect(result.current.generationTask.status).toBe('processing');
    });

    // Mock task complete
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-gen-1', status: 'completed', progress: 100 } });

    await act(async () => {
      await testMutate(['taskStatus/generation', 'task-gen-1']);
    });

    await waitFor(() => {
      expect(result.current.generating).toBe(false);
      expect(result.current.generationTask.status).toBe('completed');
      expect(mockOnChanged).toHaveBeenCalled();
    });
  });

  it('handles start knowledge graph generation and task polling transitions', async () => {
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: [] } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: { status: 'ready', knowledge_status: 'ready', chunk_count: 5 } });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: [] } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: {} });
    
    catalogService.startCourseCatalogKnowledgeGraphGeneration.mockResolvedValue({ data: { task_id: 'task-kg-1', status: 'processing' } });
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-kg-1', status: 'processing' } });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.knowledgeGraphGenerationDisabled).toBe(false);
    });

    await act(async () => {
      await result.current.handleStartKnowledgeGraphGeneration();
    });

    expect(catalogService.startCourseCatalogKnowledgeGraphGeneration).toHaveBeenCalledWith('c123');

    await waitFor(() => {
      expect(result.current.knowledgeGraphGenerating).toBe(true);
      expect(result.current.knowledgeGraphTask.task_id).toBe('task-kg-1');
    });

    // Mock task complete
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-kg-1', status: 'completed' } });

    await act(async () => {
      await testMutate(['taskStatus/kg', 'task-kg-1']);
    });

    await waitFor(() => {
      expect(result.current.knowledgeGraphGenerating).toBe(false);
      expect(result.current.knowledgeGraphTask.status).toBe('completed');
      expect(mockOnChanged).toHaveBeenCalled();
    });
  });

  it('handles start quiz generation and task polling transitions', async () => {
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: [] } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: { status: 'ready', knowledge_status: 'ready', chunk_count: 5 } });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: [] } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: {} });
    
    catalogService.startQuizGeneration.mockResolvedValue({ code: 202, data: { task_id: 'task-quiz-1' } });
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-quiz-1', status: 'processing' } });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      await result.current.handleStartQuizGeneration();
    });

    expect(catalogService.startQuizGeneration).toHaveBeenCalledWith('c123');

    await waitFor(() => {
      expect(result.current.quizGenerating).toBe(true);
      expect(result.current.quizGenTask.task_id).toBe('task-quiz-1');
    });

    // Mock task complete
    taskService.getTaskStatus.mockResolvedValue({ data: { id: 'task-quiz-1', status: 'completed' } });

    await act(async () => {
      await testMutate(['taskStatus/quiz', 'task-quiz-1']);
    });

    await waitFor(() => {
      expect(result.current.quizGenerating).toBe(false);
      expect(result.current.quizGenTask.status).toBe('completed');
      expect(mockOnChanged).toHaveBeenCalled();
    });
  });

  it('handles material deletion correctly', async () => {
    const mockMaterials = [{ id: 'm1', name: 'Material 1', status: 'uploaded' }];
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: mockMaterials } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: { material_count: 1 } });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: [] } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: {} });
    
    catalogService.deleteCourseCatalogMaterial.mockResolvedValue({ data: { knowledge_status: 'partial' } });

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.materials).toEqual(mockMaterials);
    });

    await act(async () => {
      await result.current.handleDeleteMaterial({ id: 'm1' });
    });

    expect(catalogService.deleteCourseCatalogMaterial).toHaveBeenCalledWith('c123', 'm1');
    expect(mockOnChanged).toHaveBeenCalled();
  });

  it('handles resource deletion correctly', async () => {
    const mockResources = [{ id: 'r1', title: 'Resource 1' }];
    catalogService.getCourseCatalogMaterials.mockResolvedValue({ data: { materials: [] } });
    catalogService.getCourseCatalogStatus.mockResolvedValue({ data: {} });
    catalogService.getCourseCatalogResources.mockResolvedValue({ data: { resources: mockResources } });
    catalogService.getCourseCatalogKnowledgeGraphStatus.mockResolvedValue({ data: {} });
    
    catalogService.deleteResource.mockResolvedValue({});

    const { result } = renderHook(
      () => useCatalog({ catalog: mockCatalog, open: true, onChanged: mockOnChanged }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.resources).toEqual(mockResources);
    });

    await act(async () => {
      await result.current.handleDeleteResource({ id: 'r1' });
    });

    expect(catalogService.deleteResource).toHaveBeenCalledWith('r1');
    expect(mockOnChanged).toHaveBeenCalled();
  });
});
