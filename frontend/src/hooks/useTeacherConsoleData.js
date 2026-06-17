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

export function useTeacherConsoleData(activeClass, { resourcePage = 1, resourcePageSize = 50 } = {}) {
  // Fetch classes
  const { data: classesRes, error: classesError, mutate: refreshClasses, isLoading: classesLoading } = useSWR(
    ['teachingClasses'],
    () => fetcherWrapper(teachingService.getClasses())
  );
  
  const classes = classesRes?.data || [];

  // Fetch students for active class
  const { data: studentsRes, error: studentsError, mutate: refreshStudents, isLoading: studentsLoading } = useSWR(
    activeClass ? ['classStudents', activeClass] : null,
    () => fetcherWrapper(teachingService.getClassStudents(activeClass))
  );

  const students = studentsRes?.data || [];

  // Fetch insights
  const { data: insightsRes, error: insightsError, mutate: refreshInsights, isLoading: insightsLoading } = useSWR(
    activeClass ? ['classInsights', activeClass] : null,
    () => fetcherWrapper(teachingService.getConsoleInsights(activeClass))
  );

  const insights = insightsRes?.data || null;

  // Fetch resources
  const { data: resourcesRes, error: resourcesError, mutate: refreshResources, isLoading: resourcesLoading } = useSWR(
    activeClass ? ['classResources', activeClass, resourcePage, resourcePageSize] : null,
    () => fetcherWrapper(learningService.getResources({ course_id: activeClass, page: resourcePage, page_size: resourcePageSize }))
  );

  const resources = resourcesRes?.data?.resources || [];

  return {
    classes,
    classesLoading,
    classesError: classesError ? classesError.message || '教学班加载失败' : null,
    refreshClasses,
    students,
    studentsLoading,
    studentsError: studentsError ? studentsError.message || '学生列表加载失败' : null,
    refreshStudents,
    insights,
    insightsLoading,
    insightsError: insightsError ? insightsError.message || '班级统计加载失败' : null,
    refreshInsights,
    resources,
    resourcesLoading,
    resourcesError: resourcesError ? resourcesError.message || '学习资源加载失败' : null,
    refreshResources,
  };
}
