import apiClient from '../client';

export const courseService = {
  getMyCourses() {
    return apiClient.get('/courses');
  },

  getReadyCatalogs() {
    return apiClient.get('/course-catalogs', { params: { status: 'ready' } });
  },

  // 创建教学班 (教师端)
  createCourse(data) {
    return apiClient.post('/courses', data);
  },

  // 加入教学班 (学生端)
  joinCourse(courseCode) {
    return apiClient.post('/courses/join', { course_code: courseCode });
  }
};
