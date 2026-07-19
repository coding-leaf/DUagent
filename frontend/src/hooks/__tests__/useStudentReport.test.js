import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import useStudentReport from '../useStudentReport';
import { teachingService } from '../../api/services/teaching';

vi.mock('../../api/services/teaching', () => ({
  teachingService: {
    getStudentReport: vi.fn()
  }
}));

describe('useStudentReport', () => {
  it('does not fetch when classId or studentId is missing', () => {
    const { result } = renderHook(() => useStudentReport(null, 's123'));
    expect(teachingService.getStudentReport).not.toHaveBeenCalled();
    expect(result.current.reportData).toBeUndefined();
  });

  it('fetches and returns data correctly', async () => {
    teachingService.getStudentReport.mockResolvedValue({ code: 200, data: { name: 'Test Student' } });
    const { result } = renderHook(() => useStudentReport('c1', 's1'));
    
    await waitFor(() => {
      expect(result.current.reportData).toEqual({ name: 'Test Student' });
    });
  });

  it('returns an error when the API request fails', async () => {
    teachingService.getStudentReport.mockResolvedValue({ code: 500, message: 'Server Error' });
    const { result } = renderHook(() => useStudentReport('c2', 's2'));
    
    await waitFor(() => {
      expect(result.current.error).toBeDefined();
      expect(result.current.error.message).toBe('Server Error');
      expect(result.current.error.code).toBe(500);
    });
  });
});
