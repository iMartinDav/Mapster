const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', error => console.log('BROWSER ERROR:', error.message));
  
  await page.goto('https://frontend-5mgaic6hu-martin-davila-s-projects.vercel.app');
  await page.waitForTimeout(5000);
  await browser.close();
})();
