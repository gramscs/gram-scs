const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto('http://127.0.0.1:5000/admin/login');
  await page.fill('input[name="username"]', 'admin');
  await page.fill('input[name="password"]', 'gram@2017');
  await Promise.all([
    page.waitForURL('**/admin/dashboard', { timeout: 60000 }).catch(() => {}),
    page.click('button[type="submit"]')
  ]);

  await page.goto('http://127.0.0.1:5000/admin/consignments');
  await page.waitForSelector('#sheet-body tr', { timeout: 60000 });
  await page.waitForSelector('.edit-row', { timeout: 60000 });

  // Ensure first row has identifiable data for test (in-memory via modal)
  await page.click('.edit-row');
  await page.waitForSelector('#editConsignmentModal', { state: 'visible', timeout: 60000 });

  await page.fill('#modal-consignment-number', 'AUTO-CN-001');
  await page.selectOption('#modal-status', 'In Transit');
  await page.fill('#modal-pickup-tag', 'PICKUP-TAG-X');
  await page.fill('#modal-pickup-pincode', '110017');
  await page.fill('#modal-pickup-date', '2026-05-09');
  await page.fill('#modal-drop-pincode', '400001');
  await page.fill('#modal-drop-date', '2026-05-10');
  await page.click('#modal-save-btn');

  // Re-open and verify prefill
  await page.click('.edit-row');
  await page.waitForSelector('#editConsignmentModal', { state: 'visible', timeout: 60000 });

  const values = await page.evaluate(() => ({
    consignment: document.getElementById('modal-consignment-number')?.value || '',
    status: document.getElementById('modal-status')?.value || '',
    pickupTag: document.getElementById('modal-pickup-tag')?.value || '',
    pickupPin: document.getElementById('modal-pickup-pincode')?.value || '',
    pickupDate: document.getElementById('modal-pickup-date')?.value || '',
    dropPin: document.getElementById('modal-drop-pincode')?.value || '',
    dropDate: document.getElementById('modal-drop-date')?.value || ''
  }));

  console.log('PREFILL_VALUES:' + JSON.stringify(values));
  await browser.close();
})();
