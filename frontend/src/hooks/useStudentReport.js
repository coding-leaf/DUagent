import useSWR from 'swr';
import { teachingService } from '../api/services/teaching';

export default function useStudentReport(classId, studentId) {
  const key = classId && studentId ? ['studentReport', classId, studentId] : null;
  
  const { data, error, isLoading } = useSWR(key, async ([, cid, sid]) => {
    const res = await teachingService.getStudentReport(cid, sid);
    if (res.code !== 200) throw new Error(res.message || 'Failed to fetch report');
    return res;
  });

  return {
    reportData: data?.data,
    isLoading,
    error
  };
}
