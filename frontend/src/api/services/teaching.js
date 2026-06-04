import client from '../client';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';

export const teachingService = {
  // 获取教师名下的班级/课程列表
  getClasses: async () => {
    if (useMock) {
      return client.get('/api/v1/teacher/classes');
    }
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
    if (useMock) {
      return client.get(`/api/v1/course/${courseId}/students`);
    }
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
          current_path_node: '数据结构基础',
          overall_mastery: 0.75, // Placeholder/Estimate
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
    if (useMock) {
      return client.get(`/api/v1/course/${courseId}/insights`);
    }
    return Promise.resolve({
      code: 200,
      message: 'success',
      data: {
        overview: '该班级整体进度正常。近期大部分同学在图的遍历及搜索算法上完成度较高，但在“平衡二叉树设计”章节上停留时间较长，提示此处为理解难点，建议课堂上增加代码解析课时。',
        avg_duration: 48.5,
        coverage_rate: 82,
        special_students: [
          {
            user_id: 'special_1',
            username: '王明',
            english_name: 'Wang Ming',
            avatar_text: '王',
            avatar_color: 'bg-error-container/20 text-error',
            issue: '测试正确率偏低',
            border_color: 'hover:border-error-container hover:bg-error-container/10'
          }
        ]
      }
    });
  },

  // 获取特定学生的详细学情报告
  getStudentReport: async (classId, studentId) => {
    // If only one param was passed (e.g. legacy/mock calls), adjust accordingly
    let actualClassId = classId;
    let actualStudentId = studentId;
    if (studentId === undefined) {
      actualStudentId = classId;
      actualClassId = localStorage.getItem('course_id') || 'default_course';
    }

    if (useMock) {
      return client.get(`/api/v1/teacher/students/${actualStudentId}/report`);
    }

    const res = await client.get(`/teaching/classes/${actualClassId}/students/${actualStudentId}/learning`);
    if (res.code === 200 && res.data) {
      const d = res.data;
      
      // Default coordinates fallback since summary counts are returned
      const masteredCount = d.profile_summary?.knowledge_mastered || 0;
      const weakCount = d.profile_summary?.knowledge_weak || 0;
      const coords = [];
      const sampleNames = ['二叉树遍历', '冒泡排序', '哈希函数', 'AVL树平衡', '红黑树变色', '最小生成树'];
      for (let i = 0; i < sampleNames.length; i++) {
        let type = 'learning';
        if (i < masteredCount) type = 'mastered';
        else if (i - masteredCount < weakCount) type = 'weak';
        coords.push({ name: sampleNames[i], type });
      }

      return {
        code: 200,
        message: 'success',
        data: {
          user_id: d.student?.id || actualStudentId,
          username: d.student?.real_name || d.student?.username || '李华',
          student_id: d.student?.student_id || '2023010405',
          major: '计算机科学与技术',
          class_name: '数据结构课程班',
          status: '活跃中',
          level: d.student?.guidance_level || 'L2',
          score: d.evaluation_summary?.overall_score || 75,
          total_duration_hours: d.quiz_stats?.avg_time_spent ? Math.round(d.quiz_stats.avg_time_spent / 36) : 48,
          rank: 12,
          motivation_index: 86,
          ai_diagnosis: '该生对“图表逻辑”和“代码实践”敏感度极高，建议在讲解复杂算法时增加可视化演示与即时调试环节。',
          guidance_level: d.student?.guidance_level || 'L2',
          guidance_suggestion: '检测到当前任务进度平稳，建议保持 L2 伴学以确保理解留存。',
          knowledge_coordinates: coords,
          ai_insight: '该同学在逻辑抽象与代码落地方面表现良好。特别是在线性表与树形结构章节，其通过自主练习，展现了良好的数学建模能力。近期对于图论及动态规划问题的处理存在偶尔失误，建议加强专项练习。',
          action_suggestions: [
            '推荐开启“B+树高级应用”进阶模块。',
            '参与“分布式一致性算法”智能体协作练习。',
            '定期复习“空间复杂度优化”相关错题。'
          ],
          mastery_stats: [
            { name: '基础算法逻辑', percent: d.evaluation_summary?.overall_score || 75 },
            { name: '空间复杂度分析', percent: 82 },
            { name: '工程化编码习惯', percent: 68 }
          ],
          learning_path_progress: [
            { module: '基础线性表应用', status: '已过关', time: '12h 45m', completion: '100%' },
            { module: '非线性结构: 树与森林', status: '进行中', time: '28h 10m', completion: '85%' },
            { module: '图论算法: 路径规划', status: '待开启', time: '3h 20m', completion: '15%' }
          ],
          resource_distribution: {
            avg_score: d.quiz_stats?.avg_score || 8.4,
            video: 40,
            interactive: 35,
            document: 25
          }
        }
      };
    }
    return res;
  }
};

