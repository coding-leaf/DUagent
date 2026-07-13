import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { learningActivityService } from '../../api/services/learningActivity';
import { profileService } from '../../api/services/profile';
import { useResourceStudyTracking } from '../useResourceStudyTracking';

vi.mock('../../api/services/learningActivity', () => ({
  learningActivityService: {
    minStudySeconds: 5,
    trackActivity: vi.fn()
  }
}));

vi.mock('../../api/services/profile', () => ({
  profileService: {
    refreshProfile: vi.fn()
  }
}));

describe('useResourceStudyTracking', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    learningActivityService.trackActivity.mockReset().mockResolvedValue({ code: 200 });
    profileService.refreshProfile.mockReset().mockResolvedValue({ code: 202 });
  });

  test('records shared resource study under the active class course', async () => {
    const { unmount } = renderHook(() => useResourceStudyTracking({
      courseId: 'class-course',
      resource: {
        id: 'shared-resource',
        course_id: 'catalog-host-course',
        knowledge_point: '变量与数据类型'
      },
      nodeContext: { id: 'node-1', name: '变量与数据类型' }
    }));

    expect(learningActivityService.trackActivity).toHaveBeenCalledWith(expect.objectContaining({
      activity_type: 'resource_view',
      course_id: 'class-course',
      resource_id: 'shared-resource'
    }));

    act(() => {
      vi.advanceTimersByTime(6000);
      unmount();
    });

    await waitFor(() => {
      expect(learningActivityService.trackActivity).toHaveBeenCalledWith(expect.objectContaining({
        activity_type: 'resource_study',
        course_id: 'class-course',
        duration_seconds: 6
      }));
    });
    await waitFor(() => {
      expect(profileService.refreshProfile).toHaveBeenCalledWith('class-course');
    });
  });
});
