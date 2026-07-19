import { test, expect } from '@playwright/test';

const jsonResponse = (body, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

test('Chat connection persists when navigating away and back', async ({ page }) => {
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
          name: '测试班级',
          description: '测试',
        }],
      },
    }));
  });

  await page.route(/\/api\/v1\/resources(\?.*)?$/, async (route) => {
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
  await page.waitForURL('**/dashboard');

  await page.getByTestId('nav-ai-chat').first().click();
  await page.waitForURL('**/ai-chat');

  // Find the textarea and send button
  await page.locator('textarea').fill('Persistence Test Message');
  // Click the send button via testid
  await page.getByTestId('send-message-button').click();

  // Wait for the message to appear
  await expect(page.locator('text=Persistence Test Message')).toBeVisible();

  // Navigate away
  await page.getByTestId('nav-dashboard').first().click();
  await page.waitForURL('**/dashboard');

  // Navigate back to AI chat
  await page.getByTestId('nav-ai-chat').first().click();
  await page.waitForURL('**/ai-chat');

  // Expect the message to still be there
  await expect(page.locator('text=Persistence Test Message')).toBeVisible();
});
