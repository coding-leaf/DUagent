const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  await page.goto('http://localhost:5173/');
  await page.fill('input[type="text"]', 'student_demo');
  await page.fill('input[type="password"]', '123456');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);
  
  const bodyHtml = await page.innerHTML('body');
  const hasError = bodyHtml.includes('error in text');
  
  console.log('--- DASHBOARD TEST RESULTS ---');
  console.log('Body contains error in text:', hasError);
  if (hasError) {
    const errorSvgMatch = bodyHtml.match(/<svg[^>]*error in text.*?<\/svg>/s);
    if (errorSvgMatch) {
      console.log('Found SVG:', errorSvgMatch[0].substring(0, 300) + '...');
    }
  } else {
    // try to find it via querySelector
    const svg = await page.$('svg');
    if (svg) console.log('SVG found on page, but not matching error text');
  }
  await browser.close();
})();
