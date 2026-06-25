import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useQuizEngine } from '../useQuizEngine';
import { quizService } from '../../api/services/quiz';
import { useCourse } from '../../context/CourseContext';

vi.mock('../../api/services/quiz', () => ({
  quizService: {
    getQuestions: vi.fn(),
    submitQuiz: vi.fn(),
  }
}));

vi.mock('../../api/services/learningActivity', () => ({
  learningActivityService: {
    trackActivity: vi.fn(),
  }
}));

vi.mock('../../api/services/profile', () => ({
  profileService: {
    refreshProfile: vi.fn().mockResolvedValue(),
  }
}));

vi.mock('../../context/CourseContext', () => ({
  useCourse: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  }
}));

describe('useQuizEngine', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useCourse.mockReturnValue({ activeCourseId: 'course1', courses: [] });
  });

  it('starts with loading true and becomes false after successful fetch', async () => {
    const mockQuestions = {
      quiz_id: 'quiz1',
      questions: [
        { id: 'q1', type: 'single_choice', content: 'Q1' }
      ]
    };
    quizService.getQuestions.mockResolvedValue({ code: 200, data: mockQuestions });

    const { result } = renderHook(() => useQuizEngine({ nodeId: 'node1' }));

    expect(result.current.loading).toBe(true);

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.quizData).toEqual(mockQuestions);
    expect(quizService.getQuestions).toHaveBeenCalledWith('course1', 'node1', {});
  });

  it('handles answer changes correctly for single_choice', async () => {
    const mockQuestions = {
      quiz_id: 'quiz1',
      questions: [
        { id: 'q1', type: 'single_choice', content: 'Q1' }
      ]
    };
    quizService.getQuestions.mockResolvedValue({ code: 200, data: mockQuestions });

    const { result } = renderHook(() => useQuizEngine({ nodeId: 'node1' }));

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    act(() => {
      result.current.handleAnswerChange('A');
    });

    expect(result.current.answers).toEqual({ q1: 'A' });
  });

  it('handles answer changes correctly for multiple_choice', async () => {
    const mockQuestions = {
      quiz_id: 'quiz-multiple',
      questions: [
        { id: 'q1', type: 'multiple_choice', content: 'Q1' }
      ]
    };
    quizService.getQuestions.mockResolvedValue({ code: 200, data: mockQuestions });

    const { result } = renderHook(() => useQuizEngine({ nodeId: 'node-multiple' }));

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    act(() => {
      result.current.handleAnswerChange('A');
    });

    expect(result.current.answers).toEqual({ q1: ['A'] });

    act(() => {
      result.current.handleAnswerChange('B');
    });

    expect(result.current.answers).toEqual({ q1: ['A', 'B'] });

    act(() => {
      result.current.handleAnswerChange('A');
    });

    expect(result.current.answers).toEqual({ q1: ['B'] });
  });
});
