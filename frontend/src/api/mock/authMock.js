export default function authMock(mock) {
  // GET /api/v1/auth/captcha
  mock.onGet('/auth/captcha').reply(200, {
    code: 200,
    message: 'success',
    data: {
      captcha_token: 'mock-token-' + Date.now(),
      captcha_question: '3 + 5 = ?',
    },
  });

  // POST /api/v1/auth/login
  mock.onPost('/auth/login').reply((config) => {
    const data = JSON.parse(config.data);
    
    if (data.email === 'error@domain.com') {
      return [401, {
        code: 40100,
        message: '邮箱或密码错误',
        data: null
      }];
    }

    // Role dynamic deduction based on email
    let role = 'student';
    if (data.email && data.email.includes('teacher')) {
      role = 'teacher';
    } else if (data.email && data.email.includes('admin')) {
      role = 'admin';
    }

    return [200, {
      code: 200,
      message: 'success',
      data: {
        token: 'mock-token-' + Date.now(),
        access_token: 'mock-access-token-' + Date.now(),
        refresh_token: 'mock-refresh-token',
        expires_in: 1800,
        user: {
          id: 'u-user-01',
          email: data.email,
          username: data.email ? data.email.split('@')[0] : '害虫杀手队',
          role: role,
        }
      }
    }];
  });

  // POST /api/v1/auth/register
  mock.onPost('/auth/register').reply(201, {
    code: 201,
    message: 'created',
    data: {
      user_id: 'u-new-02',
      email: 'newuser@domain.com',
      username: '新注册用户'
    }
  });
}
