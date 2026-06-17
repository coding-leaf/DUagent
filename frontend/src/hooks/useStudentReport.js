import useSWR from 'swr';
import { teachingService } from '../api/services/teaching';

export default function useStudentReport(classId, studentId) {
  const key = classId && studentId ? ['studentReport', classId, studentId] : null;
  
  const { data, error, isLoading } = useSWR(key, async ([, cid, sid]) => {
    const res = await teachingService.getStudentReport(cid, sid);
    if (res.code !== 200) {
      const err = new Error(res.message || 'Failed to fetch report');
      err.code = res.code;
      throw err;
    }
    return res;
  }, { revalidateOnFocus: false });

  return {
    reportData: data?.data,
    isLoading,
    error
  };
}
