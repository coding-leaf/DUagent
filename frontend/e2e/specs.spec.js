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

});
