const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', error => {
    errors.push(error.message);
  });

  await page.goto('http://localhost:5173/');
  await page.waitForTimeout(2000);
  
  const bodyHtml = await page.innerHTML('body');
  const hasError = bodyHtml.includes('error in text');
  
  console.log('--- TEST RESULTS ---');
  console.log('Console Errors:', errors);
  console.log('Body contains error in text:', hasError);
  if (hasError) {
    const errorSvgMatch = bodyHtml.match(/<svg[^>]*error in text.*?<\/svg>/s);
    if (errorSvgMatch) {
      console.log('Found SVG:', errorSvgMatch[0].substring(0, 300) + '...');
    }
  }
  await browser.close();
})();
