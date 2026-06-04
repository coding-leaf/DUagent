import client from '../client';

export const teachingService = {
  // 获取教师名下的班级/课程列表
  getClasses: () => {
    return client.get('/api/v1/teacher/classes');
  },
  
  // 获取某个课程的学生列表
  getClassStudents: (courseId) => {
    return client.get(`/api/v1/course/${courseId}/students`);
  },

  // 获取教师控制台的AI洞察及需重点关注学生
  getConsoleInsights: (courseId) => {
    return client.get(`/api/v1/course/${courseId}/insights`);
  },

  // 获取特定学生的详细学情报告
  getStudentReport: (studentId) => {
    return client.get(`/api/v1/teacher/students/${studentId}/report`);
  }
};
