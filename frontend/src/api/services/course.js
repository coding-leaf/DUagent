import apiClient from '../client';

export const courseService = {
  getMyCourses() {
    return apiClient.get('/courses');
  },

  // 创建课程 / 开班 (教师端)
  createCourse(data) {
    return apiClient.post('/courses', data);
  },

  // 加入课程 (学生端)
  joinCourse(courseCode) {
    return apiClient.post('/courses/join', { course_code: courseCode });
  }
};
