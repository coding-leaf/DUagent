import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useLearningEffects } from '../useLearningEffects';
import { profileService } from '../../api/services/profile';
import { learningService } from '../../api/services/learning';
import { taskService } from '../../api/services/task';
import { mutate } from 'swr';

vi.mock('../../api/services/profile', () => ({
  profileService: {
    getLearningEffects: vi.fn()
  }
}));

vi.mock('../../api/services/learning', () => ({
  learningService: {
    refreshEvaluation: vi.fn()
  }
}));

vi.mock('../../api/services/task', () => ({
  taskService: {
    getTaskStatus: vi.fn()
  }
}));

describe('useLearningEffects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mutate(() => true, undefined, { revalidate: false });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not fetch when activeCourseId is missing', () => {
    const { result } = renderHook(() => useLearningEffects(null));
    expect(profileService.getLearningEffects).not.toHaveBeenCalled();
    expect(result.current.effectsData).toBeNull();
  });

  it('fetches and returns derived states correctly', async () => {
    const mockData = {
      generated_at: '2026-06-18T00:00:00Z',
      summary_text: 'Summary of learning',
      node_progress: [
        { node_id: 'n1', node_name: 'Node 1', assessment_state: 'mastered', mastery_label: 'A', question_count: 5 },
        { node_id: 'n2', node_name: 'Node 2', assessment_state: 'pending_practice', question_count: 3 }
      ]
    };
    profileService.getLearningEffects.mockResolvedValue({ code: 200, data: mockData });
    const { result } = renderHook(() => useLearningEffects('c123'));
    
    await waitFor(() => {
      expect(result.current.effectsData).toEqual(mockData);
      expect(result.current.overview.total).toBe(2);
      expect(result.current.overview.practiced).toBe(1);
      expect(result.current.overview.pending).toBe(1);
    });
  });

  it('triggers refresh and processes SWR polling and revalidation on completion', async () => {
    const mockData = { node_progress: [] };
    profileService.getLearningEffects.mockResolvedValue({ code: 200, data: mockData });
    learningService.refreshEvaluation.mockResolvedValue({ code: 202, data: { task_id: 'task999' } });
    
    let taskCallCount = 0;
    taskService.getTaskStatus.mockImplementation(async () => {
      taskCallCount++;
      if (taskCallCount === 1) {
        return { code: 200, data: { status: 'processing', progress: 50 } };
      }
      return { code: 200, data: { status: 'completed', progress: 100 } };
    });

    const { result } = renderHook(() => useLearningEffects('c123'));
    
    await act(async () => {
      await result.current.handleRefresh();
    });

    expect(learningService.refreshEvaluation).toHaveBeenCalledWith('c123');
    expect(result.current.refreshTask?.task_id).toBe('task999');
    expect(result.current.isPolling).toBe(true);

    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    expect(taskService.getTaskStatus).toHaveBeenCalledTimes(1);
    expect(result.current.refreshTask?.status).toBe('processing');
    expect(result.current.isPolling).toBe(true);

    profileService.getLearningEffects.mockClear();

    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(taskService.getTaskStatus).toHaveBeenCalledTimes(2);
      expect(result.current.refreshTask?.status).toBe('completed');
      expect(result.current.isPolling).toBe(false);
      expect(profileService.getLearningEffects).toHaveBeenCalled();
    });
  });

  it('handles refresh evaluation API errors gracefully', async () => {
    learningService.refreshEvaluation.mockRejectedValue(new Error('Network Error'));
    const { result } = renderHook(() => useLearningEffects('c123'));
    
    await act(async () => {
      await result.current.handleRefresh();
    });

    expect(result.current.refreshTask?.status).toBe('failed');
    expect(result.current.refreshTask?.error_message).toBe('Network Error');
    expect(result.current.refreshFailed).toBe(true);
  });

  it('handles task status polling errors gracefully', async () => {
    learningService.refreshEvaluation.mockResolvedValue({ code: 202, data: { task_id: 'task999' } });
    taskService.getTaskStatus.mockRejectedValue(new Error('Polling Failed'));

    const { result } = renderHook(() => useLearningEffects('c123'));
    
    await act(async () => {
      await result.current.handleRefresh();
    });

    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    expect(result.current.refreshTask?.status).toBe('failed');
    expect(result.current.refreshTask?.error_message).toBe('Polling Failed');
    expect(result.current.refreshFailed).toBe(true);
  });
});
