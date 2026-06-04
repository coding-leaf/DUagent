/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect } from 'react';
import { courseService } from '../api/services/course';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

const CourseContext = createContext(null);

export function CourseProvider({ children }) {
  const [courses, setCourses] = useState([]);
  const [activeCourseId, setActiveCourseId] = useState(null);
  const [loading, setLoading] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const fetchCourses = async () => {
    try {
      setLoading(true);
      const res = await courseService.getMyCourses();
      if (res.code === 200 && res.data) {
        const coursesList = res.data.courses || (Array.isArray(res.data) ? res.data : []);
        setCourses(coursesList);
        
        const queryParams = new URLSearchParams(location.search);
        const urlCourseId = queryParams.get('course_id');
        const localCourseId = localStorage.getItem('course_id');
        
        let targetCourseId = null;
        if (urlCourseId && coursesList.some(c => c.id === urlCourseId)) {
          targetCourseId = urlCourseId;
        } else if (localCourseId && coursesList.some(c => c.id === localCourseId)) {
          targetCourseId = localCourseId;
        } else if (coursesList.length > 0) {
          targetCourseId = coursesList[0].id;
        }
        
        if (targetCourseId) {
          setActiveCourseId(targetCourseId);
          localStorage.setItem('course_id', targetCourseId);
        }
      }
    } catch (err) {
      console.error('获取课程列表失败:', err);
    } finally {
      setLoading(false);
    }
  };

  // Sync courses whenever authenticated user changes (login/logout/refresh)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (user) {
        fetchCourses();
      } else {
        setCourses([]);
        setActiveCourseId(null);
        setLoading(false);
      }
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Sync with URL query parameter changes
  useEffect(() => {
    if (courses.length > 0) {
      const queryParams = new URLSearchParams(location.search);
      const urlCourseId = queryParams.get('course_id');
      if (urlCourseId && courses.some(c => c.id === urlCourseId) && urlCourseId !== activeCourseId) {
        const timer = setTimeout(() => {
          setActiveCourseId(urlCourseId);
          localStorage.setItem('course_id', urlCourseId);
        }, 0);
        return () => clearTimeout(timer);
      }
    }
  }, [location.search, courses, activeCourseId]);

  const changeCourse = (courseId) => {
    setActiveCourseId(courseId);
    localStorage.setItem('course_id', courseId);

    // Sync to URL query parameters
    const searchParams = new URLSearchParams(location.search);
    searchParams.set('course_id', courseId);
    navigate({
      pathname: location.pathname,
      search: searchParams.toString()
    }, { replace: true });
  };

  return (
    <CourseContext.Provider value={{ courses, activeCourseId, loading, changeCourse, refreshCourses: fetchCourses }}>
      {children}
    </CourseContext.Provider>
  );
}

export function useCourse() {
  return useContext(CourseContext);
}
