import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useRecommendedResources } from '../useRecommendedResources';
import { learningService } from '../../api/services/learning';

vi.mock('../../api/services/learning', () => ({
  learningService: {
    getResources: vi.fn()
  }
}));

describe('useRecommendedResources', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not fetch when activeCourseId is missing', () => {
    const { result } = renderHook(() => useRecommendedResources(null, []));
    expect(learningService.getResources).not.toHaveBeenCalled();
    expect(result.current.recommendedResources).toEqual([]);
  });

  it('fetches and returns all resources when messages are empty', async () => {
    const mockResources = [
      { id: 1, title: 'Resource 1', knowledge_point: 'React' },
      { id: 2, title: 'Resource 2', knowledge_point: 'Vue' }
    ];
    learningService.getResources.mockResolvedValue({
      code: 200,
      data: { resources: mockResources }
    });

    const { result } = renderHook(() => useRecommendedResources('c123', []));

    await waitFor(() => {
      expect(result.current.recommendedResources).toEqual(mockResources);
    });
  });

  it('filters recommended resources based on active knowledge points in assistant messages', async () => {
    const mockResources = [
      { id: 1, title: 'Intro to React', knowledge_point: 'React Context' },
      { id: 2, title: 'Intro to SWR', knowledge_point: 'SWR basics' },
      { id: 3, title: 'Intro to Vue', knowledge_point: 'Vue Vuex' }
    ];
    learningService.getResources.mockResolvedValue({
      code: 200,
      data: mockResources
    });

    const messages = [
      { role: 'user', content: 'Tell me about SWR' },
      { role: 'assistant', content: 'Here is SWR information', knowledge_points: ['SWR'] }
    ];

    const { result } = renderHook(() => useRecommendedResources('c124', messages));

    await waitFor(() => {
      expect(result.current.recommendedResources).toEqual([mockResources[1]]);
    });
  });
});
