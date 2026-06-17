import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { usePracticeResult, LOADING_TEXTS } from '../usePracticeResult';
import { quizService } from '../../api/services/quiz';

vi.mock('../../api/services/quiz', () => ({
  quizService: {
    getResult: vi.fn(),
  }
}));

vi.mock('../../api/services/personalizedResources', () => ({
  personalizedResourcesService: {
    generate: vi.fn(),
  }
}));

vi.mock('../../api/services/learning', () => ({
  learningService: {
    refreshEvaluation: vi.fn().mockResolvedValue(),
  }
}));

vi.mock('../../api/services/profile', () => ({
  profileService: {
    refreshProfile: vi.fn().mockResolvedValue(),
  }
}));

describe('usePracticeResult', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('populates resultData immediately if initialResultData is provided', () => {
    const initialResultData = {
      score: 80,
      correct_count: 8,
      total_count: 10,
    };
    const { result } = renderHook(() => usePracticeResult({
      courseId: 'course1',
      initialResultData,
      quizContext: {},
      navigate: vi.fn(),
    }));

    expect(result.current.resultData).toEqual(initialResultData);
    expect(result.current.accuracy).toBe(80);
  });

  it('fetches diagnosis data after 5 seconds', async () => {
    const mockDiagnosisData = { weakness: 'math' };
    quizService.getResult.mockResolvedValue({
      code: 200,
      data: { diagnosis: mockDiagnosisData }
    });

    const { result } = renderHook(() => usePracticeResult({
      courseId: 'course1',
      initialResultData: { correct_count: 5, total_count: 10 },
      quizContext: {},
      navigate: vi.fn(),
    }));

    expect(result.current.loading).toBe(true);
    expect(result.current.diagnosisData).toBeNull();

    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(quizService.getResult).toHaveBeenCalledWith('course1');
    
    // allow pending microtasks to clear state updates
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.diagnosisData).toEqual(mockDiagnosisData);
    expect(result.current.loading).toBe(false);
  });

  it('cycles through loading texts', () => {
    const { result } = renderHook(() => usePracticeResult({
      courseId: 'course1',
      navigate: vi.fn(),
    }));

    expect(result.current.currentTextIndex).toBe(0);

    act(() => {
      vi.advanceTimersByTime(1250);
    });

    expect(result.current.currentTextIndex).toBe(1);

    act(() => {
      vi.advanceTimersByTime(1250);
    });

    expect(result.current.currentTextIndex).toBe(2);
  });
});
