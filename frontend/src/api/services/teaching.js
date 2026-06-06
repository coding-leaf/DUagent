import client from '../client';

export const teachingService = {
  // 获取教师名下的班级/课程列表
  getClasses: async () => {
    const res = await client.get('/courses');
    if (res.code === 200 && res.data && res.data.courses) {
      return {
        code: 200,
        message: 'success',
        data: res.data.courses.map(c => ({
          id: c.id,
          name: c.name,
          topic: c.description || c.name,
          students: c.student_count || 0
        }))
      };
    }
    return res;
  },
  
  // 获取某个课程的学生列表
  getClassStudents: async (courseId) => {
    const res = await client.get(`/teaching/classes/${courseId}/students`);
    if (res.code === 200 && res.data && res.data.students) {
      const adapted = res.data.students.map((s, i) => {
        const colors = ['primary', 'secondary', 'tertiary', 'error'];
        const colorType = colors[i % colors.length];
        const lastName = s.real_name ? s.real_name.charAt(0) : (s.username ? s.username.charAt(0) : '学');
        return {
          user_id: s.id,
          username: s.real_name || s.username || '学生',
          english_name: s.username || 'Student',
          student_id: s.student_id || '20260000',
          avatar_text: lastName,
          avatar_color: `bg-${colorType}-container/20 text-${colorType}`,
          major: s.major,
          grade: s.grade,
          joined_at: s.joined_at
        };
      });
      return {
        code: 200,
        message: 'success',
        data: adapted
      };
    }
    return res;
  },

  // 获取教师控制台的AI洞察及需重点关注学生
  getConsoleInsights: (courseId) => {
    return client.get(`/teaching/classes/${courseId}/insights`);
  },

  // 获取特定学生的详细学情报告
  getStudentReport: async (classId, studentId) => {
    let actualClassId = classId;
    let actualStudentId = studentId;
    if (studentId === undefined) {
      actualStudentId = classId;
      actualClassId = localStorage.getItem('course_id') || 'default_course';
    }

    return client.get(`/teaching/classes/${actualClassId}/students/${actualStudentId}/learning`);
  }
};

