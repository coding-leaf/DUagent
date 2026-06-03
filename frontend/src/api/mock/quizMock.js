export default function quizMock(mock) {
  mock.onGet('/quiz/questions').reply(200, {
    code: 200,
    message: 'success',
    data: {
      quiz_id: 'q_001',
      course_id: 'default_course',
      chapter: 'tree',
      total_count: 10,
      questions: [
        {
          id: 'q1',
          type: 'single_choice',
          content: '在含有 n 个节点的完全二叉树中，如果某节点编号为 i (1 ≤ i ≤ n)，则该节点的左孩子节点的编号是？',
          options: [
            { key: 'A', text: '2i (若 2i ≤ n)' },
            { key: 'B', text: '2i + 1 (若 2i + 1 ≤ n)' },
            { key: 'C', text: 'i / 2 (向下取整)' },
            { key: 'D', text: 'i + 1 (若 i + 1 ≤ n)' }
          ]
        },
        {
          id: 'q2',
          type: 'single_choice',
          content: '哈希表中解决冲突的链地址法，在最坏情况下的时间复杂度是？',
          options: [
            { key: 'A', text: 'O(1)' },
            { key: 'B', text: 'O(log n)' },
            { key: 'C', text: 'O(n)' },
            { key: 'D', text: 'O(n log n)' }
          ]
        },
        {
          id: 'q3',
          type: 'single_choice',
          content: '当二叉平衡树(AVL)的节点发生RR型失衡时，应该进行哪种旋转操作？',
          options: [
            { key: 'A', text: '左单旋转' },
            { key: 'B', text: '右单旋转' },
            { key: 'C', text: '先左后右双旋转' },
            { key: 'D', text: '先右后左双旋转' }
          ]
        },
        {
          id: 'q4',
          type: 'multiple_choice',
          content: '以下哪些数据结构通常被用来实现优先队列？',
          options: [
            { key: 'A', text: '单向链表' },
            { key: 'B', text: '二叉堆' },
            { key: 'C', text: '斐波那契堆' },
            { key: 'D', text: '栈' }
          ]
        },
        {
          id: 'q5',
          type: 'boolean',
          content: '红黑树的根节点必须是黑色的。',
          options: [
            { key: 'T', text: '正确' },
            { key: 'F', text: '错误' }
          ]
        },
        {
          id: 'q6',
          type: 'single_choice',
          content: '若用邻接矩阵表示包含 n 个顶点的无向图，则矩阵中非零元素的个数最多为？',
          options: [
            { key: 'A', text: 'n' },
            { key: 'B', text: 'n(n-1)' },
            { key: 'C', text: 'n(n-1)/2' },
            { key: 'D', text: 'n^2' }
          ]
        },
        {
          id: 'q7',
          type: 'single_choice',
          content: '快速排序算法在最坏情况下的时间复杂度是？',
          options: [
            { key: 'A', text: 'O(n)' },
            { key: 'B', text: 'O(n log n)' },
            { key: 'C', text: 'O(n^2)' },
            { key: 'D', text: 'O(n^3)' }
          ]
        },
        {
          id: 'q8',
          type: 'multiple_choice',
          content: '关于B+树的特性，以下说法正确的有？',
          options: [
            { key: 'A', text: '所有叶子节点都在同一层' },
            { key: 'B', text: '非叶子节点也保存真实数据' },
            { key: 'C', text: '叶子节点之间通过指针连接' },
            { key: 'D', text: '查询时间复杂度不稳定' }
          ]
        },
        {
          id: 'q9',
          type: 'boolean',
          content: '在带权有向图中求单源最短路径的 Dijkstra 算法，不能处理含有负权边的图。',
          options: [
            { key: 'T', text: '正确' },
            { key: 'F', text: '错误' }
          ]
        },
        {
          id: 'q10',
          type: 'single_choice',
          content: '解决汉诺塔问题最常用的思想是？',
          options: [
            { key: 'A', text: '动态规划' },
            { key: 'B', text: '贪心算法' },
            { key: 'C', text: '分治与递归' },
            { key: 'D', text: '回溯法' }
          ]
        }
      ]
    }
  });

  mock.onPost('/quiz/submit').reply(200, {
    code: 200,
    message: 'success',
    data: {
      quiz_id: 'q_001',
      score: 80.0,
      correct_count: 8,
      total_count: 10,
      time_spent: 340,
      per_question_results: [
        { question_id: 'q1', is_correct: true, correct_answer: 'A', explanation: '完全二叉树的性质：左孩子是 2i。' },
        { question_id: 'q2', is_correct: false, correct_answer: 'C', explanation: '极端情况下形成单链表，时间复杂度 O(n)。' },
        { question_id: 'q3', is_correct: true, correct_answer: 'A', explanation: 'RR型失衡需要进行一次左旋转。' },
        { question_id: 'q4', is_correct: true, correct_answer: ['B', 'C'], explanation: '优先队列常用二叉堆或斐波那契堆实现。' },
        { question_id: 'q5', is_correct: true, correct_answer: 'T', explanation: '红黑树的根必须是黑色。' },
        { question_id: 'q6', is_correct: true, correct_answer: 'B', explanation: '无向图边是双向的，所以最多是 n(n-1) 个非零元素。' },
        { question_id: 'q7', is_correct: false, correct_answer: 'C', explanation: '当数组已经有序时，每次划分都极端不平衡，退化为 O(n^2)。' },
        { question_id: 'q8', is_correct: true, correct_answer: ['A', 'C'], explanation: 'B+树叶子在同一层且有指针连接，非叶子节点只作索引，查询很稳定。' },
        { question_id: 'q9', is_correct: true, correct_answer: 'T', explanation: 'Dijkstra基于贪心策略，无法回溯处理负权边导致的最短路径缩短。' },
        { question_id: 'q10', is_correct: true, correct_answer: 'C', explanation: '汉诺塔是经典的递归问题。' }
      ]
    }
  });

  mock.onGet('/quiz/result').reply(200, {
    code: 200,
    message: 'success',
    data: {
      course_id: 'default_course',
      latest_quiz: {
        quiz_id: 'q_001',
        score: 80.0,
        time_spent: 340,
        created_at: new Date().toISOString()
      },
      stats: {
        total_attempts: 12,
        avg_score: 78.5,
        avg_time_spent: 280,
        score_trend: [
          { date: '2024-05-01', score: 60 },
          { date: '2024-05-05', score: 75 },
          { date: '2024-05-10', score: 85 },
          { date: '2024-05-15', score: 70 },
          { date: '2024-05-20', score: 90 },
          { date: '2024-05-25', score: 80 }
        ]
      },
      diagnosis: {
        summary: '总体表现优异，已掌握大部分基础数据结构的特性。但在排序算法复杂度分析及哈希底层原理上仍有短板。',
        weak_points: [
          { name: '最坏时间复杂度', error_rate: 65 },
          { name: '哈希冲突分析', error_rate: 50 }
        ],
        suggestions: [
          '建议重温《快速排序与归并排序的性能对比》视频',
          '尝试手写一个链地址法哈希表'
        ]
      }
    }
  });
}
