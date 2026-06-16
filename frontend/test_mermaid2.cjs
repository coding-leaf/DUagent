const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:5173/test.html');
  await page.waitForTimeout(2000);
  const bodyHtml = await page.innerHTML('body');
  console.log(bodyHtml);
  await browser.close();
})();
