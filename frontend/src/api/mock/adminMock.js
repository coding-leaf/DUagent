export default function adminMock(mock) {
  // 生成虚拟用户列表
  const generateUsers = () => {
    const roles = ['student', 'teacher', 'admin'];
    const users = [];
    for (let i = 1; i <= 55; i++) {
      const role = i === 1 ? 'admin' : (i <= 5 ? 'teacher' : 'student');
      const status = i % 15 === 0 ? 'banned' : 'active';
      users.push({
        id: `usr_${i.toString().padStart(4, '0')}`,
        username: `用户_${i}`,
        email: `user${i}@example.com`,
        role: role,
        status: status,
        last_login: `2024-05-${(i % 30) + 1}T10:00:00Z`,
        created_at: `2024-01-01T08:00:00Z`
      });
    }
    return users;
  };

  let allUsers = generateUsers();

  mock.onGet('/api/v1/admin/users').reply((config) => {
    const page = config.params?.page || 1;
    const limit = config.params?.limit || 20;
    const search = config.params?.search || '';
    
    let filtered = allUsers;
    if (search) {
      filtered = filtered.filter(u => u.username.includes(search) || u.email.includes(search));
    }
    
    const start = (page - 1) * limit;
    const end = start + limit;
    
    return [200, {
      code: 200,
      message: 'success',
      data: {
        users: filtered.slice(start, end),
        total: filtered.length,
        page,
        page_size: limit
      }
    }];
  });

  mock.onPut(/\/api\/v1\/admin\/users\/[a-zA-Z0-9_]+/).reply((config) => {
    return [200, {
      code: 200,
      message: 'success'
    }];
  });

  mock.onDelete(/\/api\/v1\/admin\/users\/[a-zA-Z0-9_]+/).reply((config) => {
    return [200, {
      code: 200,
      message: 'success'
    }];
  });

  // 模拟 Agent 调度日志
  mock.onGet('/api/v1/admin/logs/agents').reply((config) => {
    const logs = [];
    const agents = ['ORCHESTRATOR', 'CODE_AGENT', 'THEORY_AGENT', 'EVAL_AGENT'];
    const levels = ['INFO', 'WARN', 'ERROR', 'DEBUG'];
    
    for (let i = 0; i < 50; i++) {
      logs.push({
        id: `log_${i}`,
        timestamp: new Date(Date.now() - i * 5000).toISOString(),
        agent: agents[i % agents.length],
        level: levels[i % 4 === 0 ? (i % 2 === 0 ? 1 : 2) : 0],
        message: `[Task #${Math.floor(Math.random() * 1000)}] 执行状态更新: ${i % 3 === 0 ? '发现潜在逻辑错误' : '正常完成阶段处理'}`,
        metadata: {
          latency: Math.floor(Math.random() * 500) + 'ms',
          tokens_used: Math.floor(Math.random() * 1500)
        }
      });
    }

    return [200, {
      code: 200,
      message: 'success',
      data: logs
    }];
  });

  mock.onGet('/api/v1/admin/logs/system').reply((config) => {
    return [200, {
      code: 200,
      message: 'success',
      data: [
        { timestamp: new Date().toISOString(), level: 'INFO', message: 'System startup complete' },
        { timestamp: new Date().toISOString(), level: 'INFO', message: 'Connected to Redis cluster' },
        { timestamp: new Date().toISOString(), level: 'WARN', message: 'High CPU usage detected on node 3' }
      ]
    }];
  });
}
