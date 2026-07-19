export default function teachingMock(mock) {
  // 1. 获取班级列表
  mock.onGet('/api/v1/teacher/classes').reply(200, {
    code: 200,
    message: 'success',
    data: [
      { id: 'CS101-A', name: 'CS101 - A班', topic: '链表与数组', students: 28 },
      { id: 'CS101-B', name: 'CS101 - B班', topic: '二叉树与堆', students: 30 },
      { id: 'CS102-C', name: 'CS102 - C班', topic: '图论算法', students: 25 },
      { id: 'CS102-D', name: 'CS102 - D班', topic: '动态规划', students: 32 }
    ]
  });

  // 姓名库
  const lastNames = ['赵','钱','孙','李','周','吴','郑','王','陈','褚','卫','蒋','沈','韩','杨'];
  const firstNames = ['伟','芳','娜','敏','静','丽','强','磊','军','洋','勇','艳','杰','娟','涛','明','超','秀英','霞','平','刚','桂英'];
  
  const generateStudents = (count, seed) => {
    const students = [];
    for (let i = 0; i < count; i++) {
      const isExtremeLow = i === 2; // 制造一个极低分
      const isExtremeHigh = i === 5; // 制造一个满分
      const lastName = lastNames[(seed + i) % lastNames.length];
      const firstName = firstNames[(seed * i + 3) % firstNames.length];
      const name = lastName + firstName;
      
      let mastery = 0.4 + Math.random() * 0.5; // 40% ~ 90%
      if (isExtremeLow) mastery = 0.15;
      if (isExtremeHigh) mastery = 0.98;

      const colors = ['primary', 'secondary', 'tertiary', 'error'];
      const colorType = colors[i % colors.length];

      students.push({
        user_id: `u_${seed}_${i}`,
        username: name,
        english_name: `Student ${name}`,
        student_id: `2024${seed.toString().padStart(2, '0')}${i.toString().padStart(2, '0')}`,
        avatar_text: lastName,
        avatar_color: `bg-${colorType}-container/20 text-${colorType}`,
        current_path_node: ['单向链表', '双向链表', '二叉树', '红黑树', '图的遍历', '动态规划基础'][i % 6],
        overall_mastery: parseFloat(mastery.toFixed(2)),
      });
    }
    return students;
  };

  // 2. 获取班级学生列表 (动态拦截)
  mock.onGet(/\/api\/v1\/course\/[A-Za-z0-9-]+\/students/).reply(config => {
    // 简单根据 URL 的长度或特征生成不同的 seed
    const courseId = config.url.split('/')[4];
    let seed = 1;
    if (courseId.includes('B')) seed = 2;
    if (courseId.includes('C')) seed = 3;
    if (courseId.includes('D')) seed = 4;
    
    // 生成 25 ~ 30 个学生
    const studentCount = 25 + (seed * 2); 
    const students = generateStudents(studentCount, seed);

    return [200, {
      code: 200,
      message: 'success',
      data: students
    }];
  });

  // 3. 获取 AI 洞察
  mock.onGet(/\/api\/v1\/course\/[A-Za-z0-9-]+\/insights/).reply(200, {
    code: 200,
    message: 'success',
    data: {
      overview: '该班级在整体理解度方面波动较大。当前主要挑战点集中在“指针的高级操作与内存管理”。AI 智能体已自动推送了针对性的可视化沙盒练习。发现有部分学生停留时间极短，可能是遇到了瓶颈。',
      avg_duration: 52.4,
      coverage_rate: 85,
      special_students: [
        {
          user_id: 'u_1_2',
          username: '孙娜',
          english_name: 'Sun Na',
          avatar_text: '孙',
          avatar_color: 'bg-error-container/20 text-error',
          issue: '掌握度极低 (15%)',
          border_color: 'hover:border-error-container hover:bg-error-container/10'
        },
        {
          user_id: 'u_1_5',
          username: '吴丽',
          english_name: 'Wu Li',
          avatar_text: '吴',
          avatar_color: 'bg-primary-container/20 text-primary',
          issue: '掌握度极高 (98%)',
          border_color: 'hover:border-primary-container hover:bg-primary-container/10'
        },
        {
          user_id: 'u_1_12',
          username: '韩杰',
          english_name: 'Han Jie',
          avatar_text: '韩',
          avatar_color: 'bg-error-container/20 text-error',
          issue: '错误率连续 5 次异常',
          border_color: 'hover:border-error-container hover:bg-error-container/10'
        }
      ]
    }
  });

  // 4. 获取特定学生的详尽报告
  mock.onGet(/\/api\/v1\/teacher\/students\/[A-Za-z0-9_]+\/report/).reply(200, {
    code: 200,
    message: 'success',
    data: {
      user_id: 'u_01',
      username: '动态学生',
      student_id: '2023010405',
      major: '计算机科学与技术',
      class_name: '数据结构 (测试班)',
      status: '活跃中',
      level: 'L9',
      score: 89,
      total_duration_hours: 124,
      rank: 15,
      motivation_index: 89,
      ai_diagnosis: '该生对“图表逻辑”和“代码实践”敏感度极高，建议在讲解复杂算法时增加可视化演示与即时调试环节。',
      guidance_level: 'L2',
      guidance_suggestion: '检测到当前任务为“红黑树”，建议保持 L2 以确保认知留存，有助于理解平衡旋转逻辑。',
      knowledge_coordinates: [
        { name: '二叉树遍历', type: 'mastered' },
        { name: '冒泡排序', type: 'mastered' },
        { name: '哈希函数', type: 'learning' },
        { name: 'AVL树平衡', type: 'weak' },
        { name: '红黑树变色', type: 'weak' },
        { name: '最小生成树', type: 'weak' }
      ],
      ai_insight: '该同学在逻辑抽象与代码落地方面表现卓越。特别是在“非线性结构”章节，其通过自主推导多叉树高度平衡算法，展现了超出同龄人的数学建模能力。近期对于“动态内存管理”与“指针悬挂”问题的处理存在偶尔失误，主要集中在底层C语言实现的细枝末节处。建议加强《内存安全与复杂数据结构》专项练习。',
      action_suggestions: [
        '推荐开启“B+树高级应用”进阶模块。',
        '参与“分布式一致性算法”智能体协作练习。',
        '定期复习“空间复杂度优化”相关错题。'
      ],
      mastery_stats: [
        { name: '基础算法逻辑', percent: 95 },
        { name: '空间复杂度分析', percent: 82 },
        { name: '工程化编码习惯', percent: 68 }
      ],
      learning_path_progress: [
        { module: '基础线性表应用', status: '已过关', time: '12h 45m', completion: '100%' },
        { module: '非线性结构: 树与森林', status: '进行中', time: '28h 10m', completion: '85%' },
        { module: '图论算法: 路径规划', status: '待开启', time: '3h 20m', completion: '15%' }
      ],
      resource_distribution: {
        avg_score: 8.4,
        video: 40,
        interactive: 35,
        document: 25
      }
    }
  });
};
