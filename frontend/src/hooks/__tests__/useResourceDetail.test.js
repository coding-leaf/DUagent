import React from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SWRConfig } from 'swr';
import { useResourceDetail } from '../useResourceDetail';
import { learningService } from '../../api/services/learning';

vi.mock('../../api/services/learning', () => ({
  learningService: {
    getResourceDetail: vi.fn()
  }
}));

const createWrapper = () => {
  return ({ children }) => React.createElement(
    SWRConfig,
    { value: { provider: () => new Map(), dedupingInterval: 0 } },
    children
  );
};

describe('useResourceDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not fetch when id is missing', () => {
    const { result } = renderHook(() => useResourceDetail(null), {
      wrapper: createWrapper()
    });
    expect(learningService.getResourceDetail).not.toHaveBeenCalled();
    expect(result.current.resource).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it('fetches and returns resource detail when id is provided', async () => {
    const mockResource = { id: 'r123', title: 'Test Resource', content: 'Resource content' };
    learningService.getResourceDetail.mockResolvedValue({
      code: 200,
      data: mockResource
    });

    const { result } = renderHook(() => useResourceDetail('r123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.resource).toEqual(mockResource);
      expect(result.current.loading).toBe(false);
    });
  });

  it('returns error when fetch fails', async () => {
    const errorMsg = 'Failed to fetch resource';
    learningService.getResourceDetail.mockResolvedValue({
      code: 500,
      message: errorMsg
    });

    const { result } = renderHook(() => useResourceDetail('r123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.resource).toBeNull();
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error.message).toBe(errorMsg);
    });
  });
});
