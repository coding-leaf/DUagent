export default function profileMock(mock) {
  mock.onGet('/profile/student').reply(200, {
    code: 200,
    message: 'success',
    data: {
      user_id: 'u_123',
      name: 'Elara Vance',
      avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBTg47lCOZc44Rlbp-24EwwN1J7sw9qUGrEClZifNn2yEyMt3okEbKNeNk18UX3gnhRFnUqxiymGyo3rL5MABT0fuopo662xIbp65CFju53RoA6l2pZXVgSgjBxCPT4X4lU-o1LuDtdBELLv78_N-q2mEKlbxJRmmCL9Y2K4b9uTOGdt--9KeTRfuTkr6rxCoUCoNPgytsazeMrZQJrccuvaETuIbMLP5YXtAHczyNNTuNHoL46_YW7s34lyn78eafbottYcLIRSeWv',
      level: 14,
      title: 'Architect',
      current_course: '数据结构与算法分析',
      learning_motivation: 89,
      motivation_percentile: 92,
      modality_preference: {
        visual: 40,
        auditory: 20,
        reading: 30,
        kinesthetic: 10
      },
      granularity_level: 'L2',
      system_suggestion: '检测到当前任务为“红黑树”，建议保持 L2 以确保认知留存，有助于理解平衡旋转逻辑。'
    }
  });

  mock.onGet('/evaluation/learning-effects').reply(200, {
    code: 200,
    message: 'success',
    data: {
      weekly_max_accuracy: 94,
      total_duration_hours: 12.5,
      knowledge_nodes: [
        { name: '二叉搜索树', status: 'mastered' },
        { name: '快速排序', status: 'mastered' },
        { name: '哈希桶', status: 'familiar' },
        { name: 'B+树分裂逻辑', status: 'weak' },
        { name: '图的拓扑排序', status: 'blind_spot' },
        { name: '最小生成树(Prim)', status: 'weak' }
      ],
      cognitive_growth: [
        { month: '1月', value: 40 },
        { month: '2月', value: 55 },
        { month: '3月', value: 35 },
        { month: '4月', value: 70 },
        { month: '5月', value: 85 },
        { month: '6月', value: 95 },
        { month: '7月', value: 60 },
        { month: '8月', value: 45 },
        { month: '9月', value: 75 },
        { month: '10月', value: 30 },
        { month: '11月', value: 50 },
        { month: '12月', value: 65 }
      ]
    }
  });
}
