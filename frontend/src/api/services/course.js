import apiClient from '../client';

export const courseService = {
  getMyCourses() {
    return apiClient.get('/courses');
  },
  
  getCourseStudents(courseId) {
    return apiClient.get(`/course/${courseId}/students`);
  },

  // 创建课程 / 开班 (教师端)
  createCourse(data) {
    return apiClient.post('/courses', data);
  },

  // 加入课程 (学生端)
  joinCourse(inviteCode) {
    return apiClient.post('/courses/join', { invite_code: inviteCode });
  }
};
