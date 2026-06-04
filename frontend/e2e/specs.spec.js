import { test, expect } from '@playwright/test';

// Arithmetic Captcha solver for automated login
const solveCaptcha = (question) => {
  const match = question.match(/(\d+)\s*([+\-*])\s*(\d+)/);
  if (!match) return "0";
  const num1 = parseInt(match[1]);
  const op = match[2];
  const num2 = parseInt(match[3]);
  if (op === '+') return String(num1 + num2);
  if (op === '-') return String(num1 - num2);
  if (op === '*') return String(num1 * num2);
  return "0";
};

const loginUser = async (page, email, password) => {
  await page.goto('/');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);

  // Solve Captcha dynamically
  const captchaEl = page.locator('button[title="点击刷新验证码"]');
  await captchaEl.waitFor({ state: 'visible' });
  const question = await captchaEl.innerText();
  const answer = solveCaptcha(question);
  await page.fill('input[placeholder="输入计算结果"]', answer);

  // Click login
  await page.click('button[type="submit"]');
};

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

});
