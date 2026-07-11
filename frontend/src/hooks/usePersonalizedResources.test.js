import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { personalizedResourcesService } from '../api/services/personalizedResources';
import usePersonalizedResources from './usePersonalizedResources';

vi.mock('../api/services/personalizedResources', () => ({
  personalizedResourcesService: {
    list: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('usePersonalizedResources', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads items and exposes generation review metadata', async () => {
    personalizedResourcesService.list.mockResolvedValue({
      code: 200,
      data: {
        items: [{ id: 'link-1', resource_type: 'diagram', review_decision: 'approved_with_advice' }],
        total: 1,
        processing_count: 0,
      },
    });

    const { result } = renderHook(() => usePersonalizedResources('course-1', 'all'));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.items[0].resource_type).toBe('diagram');
    expect(result.current.total).toBe(1);
  });
});
