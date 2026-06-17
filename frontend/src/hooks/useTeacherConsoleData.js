import useSWR from 'swr';
import { teachingService } from '../api/services/teaching';
import { learningService } from '../api/services/learning';

const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200) {
    throw new Error(res.message || '请求失败');
  }
  return res;
};

export function useTeacherConsoleData(activeClass) {
  // Fetch classes
  const { data: classesRes, error: classesError, mutate: refreshClasses, isLoading: classesLoading } = useSWR(
    ['teachingClasses'],
    () => fetcherWrapper(teachingService.getClasses())
  );
  
  const classes = classesRes?.data || [];

  // Fetch students for active class
  const { data: studentsRes, error: studentsError, isLoading: studentsLoading } = useSWR(
    activeClass ? ['classStudents', activeClass] : null,
    () => fetcherWrapper(teachingService.getClassStudents(activeClass))
  );

  const students = studentsRes?.data || [];

  // Fetch insights
  const { data: insightsRes, error: insightsError, isLoading: insightsLoading } = useSWR(
    activeClass ? ['classInsights', activeClass] : null,
    () => fetcherWrapper(teachingService.getConsoleInsights(activeClass))
  );

  const insights = insightsRes?.data || null;

  // Fetch resources
  const { data: resourcesRes, error: resourcesError, isLoading: resourcesLoading } = useSWR(
    activeClass ? ['classResources', activeClass] : null,
    () => fetcherWrapper(learningService.getResources({ course_id: activeClass, page: 1, page_size: 50 }))
  );

  const resources = resourcesRes?.data?.resources || [];

  return {
    classes,
    classesLoading,
    classesError: classesError ? '教学班加载失败' : null,
    refreshClasses,
    students,
    studentsLoading,
    studentsError: studentsError ? '学生列表加载失败' : null,
    insights,
    insightsLoading,
    insightsError: insightsError ? '班级统计加载失败' : null,
    resources,
    resourcesLoading,
    resourcesError: resourcesError ? '学习资源加载失败' : null,
  };
}
