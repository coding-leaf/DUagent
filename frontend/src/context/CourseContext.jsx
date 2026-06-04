/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect } from 'react';
import { courseService } from '../api/services/course';
import { useLocation } from 'react-router-dom';

const CourseContext = createContext(null);

export function CourseProvider({ children }) {
  const [courses, setCourses] = useState([]);
  const [activeCourseId, setActiveCourseId] = useState(null);
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  const fetchCourses = async () => {
    try {
      const res = await courseService.getMyCourses();
      if (res.code === 200 && res.data) {
        setCourses(res.data);
        
        const queryParams = new URLSearchParams(location.search);
        const urlCourseId = queryParams.get('course_id');
        const localCourseId = localStorage.getItem('course_id');
        
        let targetCourseId = null;
        if (urlCourseId && res.data.some(c => c.id === urlCourseId)) {
          targetCourseId = urlCourseId;
        } else if (localCourseId && res.data.some(c => c.id === localCourseId)) {
          targetCourseId = localCourseId;
        } else if (res.data.length > 0) {
          targetCourseId = res.data[0].id;
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

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCourses();
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
