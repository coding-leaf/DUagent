import { test, expect } from '@playwright/test';

// Arithmetic Captcha solver for automated login
const solveCaptcha = (question) => {
  const match = question.match(/(\d+)\s*([+\-*])\s*(\d+)/);
  if (!match) {
    throw new Error(`Failed to parse captcha question: "${question}"`);
  }
  const num1 = parseInt(match[1]);
  const op = match[2];
  const num2 = parseInt(match[3]);
  if (op === '+') return String(num1 + num2);
  if (op === '-') return String(num1 - num2);
  if (op === '*') return String(num1 * num2);
  throw new Error(`Unknown captcha operator: "${op}"`);
};

const loginUser = async (page, email, password) => {
  await page.goto('/');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);

  // Solve Captcha dynamically
  const captchaEl = page.locator('button[title="点击刷新验证码"]');
  await captchaEl.waitFor({ state: 'visible' });
  await expect(captchaEl).toHaveText(/^\d+\s*[-+*]\s*\d+\s*=\s*\?\s*$/, { timeout: 5000 });
  const question = await captchaEl.innerText();
  const answer = solveCaptcha(question);
  await page.fill('input[placeholder="输入计算结果"]', answer);

  // Click login
  await page.click('button[type="submit"]');
};

const jsonResponse = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

test.describe('Vite Multi-Agent Learning System E2E Suite', () => {

  test('UseCase 1: Student login -> auto enters course resources', async ({ page }) => {
    // 1. Fill login credentials for student
    await loginUser(page, 's@t.com', 'Abc12345');

    // 2. Assert redirection to Student Dashboard
    await page.waitForURL('**/dashboard');
    await expect(page).toHaveURL(/.*dashboard/);

    // 3. Assert active course loads resource cards or empty status
    const selectEl = page.locator('select');
    await expect(selectEl).toBeVisible();

    const h1El = page.locator('h1:has-text("资源库")');
    await expect(h1El).toBeVisible();

    // 验证资源卡片或空状态可见
    const resourceCard = page.locator('[data-testid="resource-card"]').first();
    const resourcesEmpty = page.locator('[data-testid="resources-empty"]');
    await expect(resourceCard.or(resourcesEmpty).first()).toBeVisible();
  });

  test('Student dashboard shows preparation copy when active course has no resources', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-student-token');
      localStorage.setItem('course_id', 'course-empty-e2e');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'student-empty-e2e',
          email: 'student@example.com',
          username: 'Student E2E',
          role: 'student',
        },
      }));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'course-empty-e2e',
            name: '空资源教学班',
            description: '有课程但暂无学习资源',
          }],
        },
      }));
    });

    await page.route(/\/api\/v1\/resources(\?.*)?$/, async (route) => {
      expect(route.request().method()).toBe('GET');
      const url = new URL(route.request().url());
      expect(url.searchParams.get('course_id')).toBe('course-empty-e2e');
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          resources: [],
          total: 0,
          page: 1,
          page_size: 50,
        },
      }));
    });

    await page.goto('/dashboard');

    await expect(page.getByText('暂无课程')).toHaveCount(0);
    await expect(page.getByTestId('resources-empty')).toBeVisible();
    await expect(page.getByTestId('resources-empty').getByText('课程资源正在准备中')).toBeVisible();
    await expect(page.getByTestId('resources-empty').getByText('请稍后查看')).toBeVisible();
  });

  test('UseCase 2: Student switches course -> views learning path & quiz', async ({ page }) => {
    // 1. Log in student
    await loginUser(page, 's@t.com', 'Abc12345');
    await page.waitForURL('**/dashboard');

    // 2. Select another course if available
    const selectEl = page.locator('select');
    await expect(selectEl).toBeVisible();
    const optionCount = await selectEl.locator('option').count();
    expect(optionCount).toBeGreaterThanOrEqual(2);
    await selectEl.selectOption({ index: 1 });
    await page.waitForSelector('[data-testid="resource-card"], [data-testid="resources-empty"]');

    // 3. Click navigation for Learning Path
    await page.click('a:has-text("路径规划")');
    await page.waitForURL('**/learning-path');
    await expect(page).toHaveURL(/.*learning-path/);

    // 4. Go to online testing
    await page.goto('/quiz');
    await page.waitForURL('**/quiz');
    await expect(page).toHaveURL(/.*quiz/);

    // 验证题目或空状态可见
    const quizQuestion = page.locator('[data-testid="quiz-question"]');
    const quizEmpty = page.locator('[data-testid="quiz-empty"]');
    await expect(quizQuestion.or(quizEmpty).first()).toBeVisible();
  });

  test('UseCase 3: Teacher login -> switches course -> views student report', async ({ page }) => {
    // 1. Log in teacher
    await loginUser(page, 't@t.com', 'Abc12345');

    // 2. Assert redirects to teacher console
    await page.waitForURL('**/teacher');
    await expect(page).toHaveURL(/.*teacher/);

    // 3. Choose another class/course button
    const classButtons = page.locator('button:has-text("班")');
    if (await classButtons.count() > 1) {
      await classButtons.nth(1).click();
      await page.waitForSelector('[data-testid="student-card"]');
    }

    // 4. Click a student card from the monitor roster to open the report
    const studentCard = page.locator('[data-testid="student-card"]').first();
    await expect(studentCard).toBeVisible();
    await studentCard.click();

    // 5. Assert report loads with query params in URL
    await page.waitForURL('**/teacher/report*');
    await expect(page).toHaveURL(/.*teacher\/report\?course_id=.*&student_id=.*/);

    // 6. Assert authentic panels are loaded
    await expect(page.locator('h3:has-text("在线测试统计")')).toBeVisible();
    await expect(page.locator('h3:has-text("学习路径进度")')).toBeVisible();
  });

  test('Admin course catalog ingestion polling retries task query failure', async ({ page }) => {
    let ingestionStarted = false;
    let taskPollCount = 0;

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-admin-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'admin-e2e',
          email: 'admin@example.com',
          username: 'Admin E2E',
          role: 'admin',
        },
      }));
    });

    await page.route('**/api/v1/admin/users**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { users: [] },
      }));
    });

    await page.route('**/api/v1/admin/logs/**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { logs: [] },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fallback();
        return;
      }

      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          catalogs: [{
            id: 'catalog-e2e',
            title: 'E2E 资源库',
            description: '任务轮询回归测试',
            status: 'ready',
            knowledge_status: ingestionStarted ? 'ingesting' : 'dirty',
            material_count: 1,
            chunk_count: 0,
            created_at: '2026-06-08T10:00:00Z',
          }],
          total: 1,
          page: 1,
          page_size: 20,
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/materials', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          materials: [{
            id: 'material-e2e',
            filename: 'lesson.md',
            source_type: 'file',
            file_size: 128,
            status: ingestionStarted && taskPollCount >= 2 ? 'ingested' : 'uploaded',
            chunk_count: ingestionStarted && taskPollCount >= 2 ? 4 : 0,
            created_at: '2026-06-08T10:01:00Z',
          }],
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/knowledge-status', async (route) => {
      const completed = ingestionStarted && taskPollCount >= 2;
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          status: 'ready',
          knowledge_status: completed ? 'ready' : 'dirty',
          material_count: 1,
          chunk_count: completed ? 4 : 0,
          pending_material_count: completed ? 0 : 1,
          failed_material_count: 0,
          last_ingestion_task_id: ingestionStarted ? 'task-e2e' : null,
          last_ingestion_status: completed ? 'completed' : 'processing',
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/ingestions', async (route) => {
      ingestionStarted = true;
      await route.fulfill(jsonResponse({
        code: 202,
        message: 'accepted',
        data: {
          task_id: 'task-e2e',
          catalog_id: 'catalog-e2e',
          status: 'processing',
        },
      }, 202));
    });

    await page.route('**/api/v1/tasks/task-e2e', async (route) => {
      taskPollCount += 1;
      if (taskPollCount === 1) {
        await route.fulfill(jsonResponse({
          code: 500,
          message: 'temporary task query failure',
          data: null,
        }, 500));
        return;
      }

      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          task_id: 'task-e2e',
          task_type: 'course_catalog_ingestion',
          status: 'completed',
          progress: 100,
        },
      }));
    });

    await page.goto('/admin');
    await page.getByRole('button', { name: '课程资源库' }).click();
    await page.getByRole('button', { name: '管理资料' }).click();
    await expect(page.getByTestId('catalog-drawer')).toBeVisible();
    await expect(page.getByText('资料列表')).toBeVisible();
    await expect(page.getByText('已上传')).toBeVisible();

    await page.getByTestId('catalog-start-ingestion').click();

    await expect(page.getByText(/任务状态查询失败.*正在重试/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('catalog-task-status').getByText('失败')).toHaveCount(0);

    await expect(page.getByTestId('catalog-task-status').getByText('已完成')).toBeVisible({ timeout: 7000 });
    expect(taskPollCount).toBeGreaterThanOrEqual(2);
  });

  test('Admin course catalog resource generation and soft delete uses declared admin endpoints', async ({ page }) => {
    let generationStarted = false;
    let generationPollCount = 0;
    let materialDeleted = false;
    const resources = [{
      id: 'resource-e2e-a',
      course_id: 'class-e2e',
      title: '二叉树讲义',
      type: 'document',
      description: '已有资源',
      tags: ['tree'],
      chapter: '树',
      knowledge_point: '二叉树',
      view_count: 0,
      created_at: '2026-06-09T09:00:00Z',
    }];

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-admin-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'admin-e2e',
          email: 'admin@example.com',
          username: 'Admin E2E',
          role: 'admin',
        },
      }));
    });

    await page.route('**/api/v1/admin/users**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { users: [] },
      }));
    });

    await page.route('**/api/v1/admin/logs/**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { logs: [] },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.fallback();
        return;
      }

      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          catalogs: [{
            id: 'catalog-e2e',
            title: 'E2E 资源库',
            description: '资源生成回归测试',
            status: 'ready',
            knowledge_status: materialDeleted ? 'dirty' : 'partial',
            material_count: materialDeleted ? 0 : 1,
            chunk_count: 6,
            created_at: '2026-06-09T08:00:00Z',
          }],
          total: 1,
          page: 1,
          page_size: 20,
        },
      }));
    });

    await page.route(/\/api\/v1\/admin\/course-catalogs\/catalog-e2e\/materials(\?.*)?$/, async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          materials: materialDeleted ? [] : [{
            id: 'material-e2e',
            filename: 'lesson.md',
            source_type: 'file',
            file_size: 128,
            status: 'ingested',
            chunk_count: 6,
            created_at: '2026-06-09T08:01:00Z',
          }],
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/materials/material-e2e', async (route) => {
      materialDeleted = true;
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'deleted',
        data: {
          id: 'material-e2e',
          catalog_id: 'catalog-e2e',
          deleted: true,
          knowledge_status: 'dirty',
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/knowledge-status', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          status: 'ready',
          knowledge_status: materialDeleted ? 'dirty' : 'partial',
          material_count: materialDeleted ? 0 : 1,
          chunk_count: 6,
          pending_material_count: 0,
          failed_material_count: 0,
          last_ingestion_task_id: null,
          last_ingestion_status: null,
        },
      }));
    });

    await page.route(/\/api\/v1\/admin\/course-catalogs\/catalog-e2e\/resources(\?.*)?$/, async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          resources,
          total: resources.length,
          page: 1,
          page_size: 20,
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/resources/generations', async (route) => {
      generationStarted = true;
      const payload = route.request().postDataJSON();
      expect(payload).toEqual({
        chapter: '树',
        knowledge_point: '二叉树',
        resource_types: ['document', 'mindmap'],
      });
      await route.fulfill(jsonResponse({
        code: 202,
        message: 'accepted',
        data: {
          task_id: 'generation-task-e2e',
          catalog_id: 'catalog-e2e',
          status: 'processing',
        },
      }, 202));
    });

    await page.route('**/api/v1/tasks/generation-task-e2e', async (route) => {
      generationPollCount += 1;
      if (generationStarted && generationPollCount >= 2 && resources.length === 1) {
        resources.push({
          id: 'resource-e2e-b',
          course_id: 'class-e2e',
          title: '二叉树导图',
          type: 'mindmap',
          description: '生成资源',
          tags: ['tree', 'mindmap'],
          chapter: '树',
          knowledge_point: '二叉树',
          view_count: 0,
          created_at: '2026-06-09T09:03:00Z',
        });
      }

      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          task_id: 'generation-task-e2e',
          task_type: 'resource_generation',
          status: generationPollCount >= 2 ? 'completed' : 'processing',
          progress: generationPollCount >= 2 ? 100 : 35,
        },
      }));
    });

    await page.route('**/api/v1/admin/resources/resource-e2e-a', async (route) => {
      const index = resources.findIndex((resource) => resource.id === 'resource-e2e-a');
      if (index >= 0) resources.splice(index, 1);
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'deleted',
        data: {
          id: 'resource-e2e-a',
          deleted: true,
        },
      }));
    });

    await page.goto('/admin');
    await page.getByRole('button', { name: '课程资源库' }).click();
    await page.getByRole('button', { name: '管理资料' }).click();

    await expect(page.getByTestId('catalog-drawer')).toBeVisible();
    await expect(page.getByRole('heading', { name: '生成学习资源' })).toBeVisible();
    await expect(page.getByText('二叉树讲义')).toBeVisible();

    await page.getByPlaceholder('章节').fill('树');
    await page.getByPlaceholder('知识点').fill('二叉树');
    await page.getByLabel('文档').check();
    await page.getByLabel('思维导图').check();
    await expect(page.getByRole('button', { name: '生成资源' })).toBeEnabled();
    await page.getByRole('button', { name: '生成资源' }).click();

    await expect(page.getByTestId('catalog-generation-task-status').getByText('处理中')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('catalog-generation-task-status').getByText('已完成')).toBeVisible({ timeout: 7000 });
    await expect(page.getByText('二叉树导图')).toBeVisible();
    expect(generationPollCount).toBeGreaterThanOrEqual(2);

    await page.getByTestId('catalog-resource-row').filter({ hasText: '二叉树讲义' }).getByRole('button', { name: '删除资源' }).click();
    await expect(page.getByText('二叉树讲义')).toHaveCount(0);

    await page.getByTestId('catalog-material-row').filter({ hasText: 'lesson.md' }).getByRole('button', { name: '删除资料' }).click();
    await expect(page.getByText('lesson.md')).toHaveCount(0);
    await expect(page.getByText('知识库 待更新')).toBeVisible();
  });

  test('Teacher console does not expose resource generation entry', async ({ page }) => {
    let deprecatedGenerateRequests = 0;

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-teacher-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'teacher-e2e',
          email: 'teacher@example.com',
          username: 'Teacher E2E',
          role: 'teacher',
        },
      }));
    });

    await page.route('**/api/v1/resources/generate', async (route) => {
      deprecatedGenerateRequests += 1;
      await route.fulfill(jsonResponse({
        code: 410,
        message: 'deprecated',
        data: null,
      }, 410));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'class-e2e',
            name: '一班',
            description: '数据结构',
            student_count: 1,
            catalog_id: 'catalog-e2e',
            catalog_title: 'E2E 资源库',
          }],
        },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-e2e/students', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          students: [{
            id: 'student-e2e',
            username: 'student',
            real_name: '学生',
            student_id: '20260001',
          }],
        },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-e2e/insights', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          summary: {},
          attention_students: [],
        },
      }));
    });

    await page.goto('/teacher');

    await expect(page.getByRole('heading', { name: '教学班选择' })).toBeVisible();
    await expect(page.getByRole('button', { name: '生成资源' })).toHaveCount(0);
    await expect(page.getByText('生成学习资源')).toHaveCount(0);
    expect(deprecatedGenerateRequests).toBe(0);
  });

  test('AI Chat renders historical messages with object-shaped knowledge points', async ({ page }) => {
    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-student-token');
      localStorage.setItem('course_id', 'course-e2e');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'student-e2e',
          email: 'student@example.com',
          username: 'Student E2E',
          role: 'student',
        },
      }));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'course-e2e',
            title: '数据结构',
            description: 'AIChat 历史渲染回归测试',
          }],
        },
      }));
    });

    await page.route('**/api/v1/tutoring/conversations**', async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/conversation-e2e')) {
        await route.fulfill(jsonResponse({
          code: 200,
          message: 'success',
          data: {
            id: 'conversation-e2e',
            title: '红黑树答疑',
            scope: 'course',
            course_id: 'course-e2e',
            messages: [{
              id: 'msg-user-e2e',
              role: 'user',
              content: '红黑树旋转怎么理解？',
              knowledge_points: [],
              diagrams: [],
            }, {
              id: 'msg-ai-e2e',
              role: 'assistant',
              content: '可以从局部平衡调整理解。',
              knowledge_points: [{
                name: '红黑树旋转',
                chapter: '树',
                mastery: 0.42,
              }],
              diagrams: [],
              suggestions: [{
                title: '继续解释插入修复',
              }],
            }],
            created_at: '2026-06-08T12:00:00Z',
            updated_at: '2026-06-08T12:01:00Z',
          },
        }));
        return;
      }

      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          conversations: [{
            id: 'conversation-e2e',
            title: '红黑树答疑',
            scope: 'course',
            course_id: 'course-e2e',
            updated_at: '2026-06-08T12:00:00Z',
          }],
          total: 1,
          page: 1,
          page_size: 20,
        },
      }));
    });

    await page.goto('/ai-chat');

    await expect(page.getByRole('heading', { name: 'DS 智能答疑专家' })).toBeVisible();
    await expect(page.getByText('可以从局部平衡调整理解。')).toBeVisible();
    await expect(page.getByText('红黑树旋转', { exact: true })).toBeVisible();
    await expect(page.getByText('继续解释插入修复', { exact: true })).toBeVisible();

    expect(consoleErrors.join('\n')).not.toContain('Objects are not valid as a React child');
    expect(consoleErrors.join('\n')).not.toContain('Each child in a list should have a unique "key" prop');
  });

});
