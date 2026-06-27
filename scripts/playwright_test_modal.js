const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Login
  await page.goto('http://127.0.0.1:5000/admin/login');
  await page.fill('input[name="username"]', 'admin');
  await page.fill('input[name="password"]', 'gram@2017');
  await Promise.all([
    page.waitForURL('**/admin/dashboard', { timeout: 60000 }).catch(() => {}),
    page.click('button[type="submit"]')
  ]);

  // Navigate to consignments page
  await page.goto('http://127.0.0.1:5000/admin/consignments');
  await page.waitForSelector('#sheet-body tr');

  // Click the first edit button
  const editBtn = await page.$('.edit-row');
  if (!editBtn) {
    console.log('NO_EDIT_BUTTON');
    await browser.close();
    process.exit(1);
  }
  await editBtn.click();

  // Wait for modal and input
  await page.waitForSelector('#editConsignmentModal', { state: 'visible', timeout: 10000 }).catch(e => {});
  const input = await page.$('#modal-consignment-number');
  if (!input) {
    console.log('NO_INPUT_FIELD');
    await browser.close();
    process.exit(1);
  }

  // Try typing
    // Inspect properties before typing
    const isVisible = await input.isVisible();
    const isEnabled = await input.isEnabled();
    const readonlyAttr = await input.getAttribute('readonly');
    const disabledAttr = await input.getAttribute('disabled');
    console.log('PROPS: visible=' + isVisible + ', enabled=' + isEnabled + ', readonly=' + readonlyAttr + ', disabled=' + disabledAttr);

    // Check computed style and bounding box
    const computed = await input.evaluate((el) => {
      const cs = window.getComputedStyle(el);
      return {
        pointerEvents: cs.pointerEvents,
        opacity: cs.opacity,
        visibility: cs.visibility,
        display: cs.display,
        readonly: el.readOnly,
      };
    });
    const box = await input.boundingBox();
    console.log('COMPUTED:', computed, 'BOX:', box);
    if (box) {
      const cx = box.x + box.width/2;
      const cy = box.y + box.height/2;
      const topEl = await page.evaluate(({cx,cy}) => {
        const el = document.elementFromPoint(cx, cy);
        return el ? {tag: el.tagName, id: el.id, classes: el.className} : null;
      }, {cx, cy});
      console.log('TOP_ELEMENT_AT_CENTER:', topEl);
    }

    // Try typing
    try {
      await input.fill('TEST-TYPED-123');
      const val = await input.inputValue();
      console.log('INPUT_VALUE:' + val);
    } catch (err) {
      console.log('FILL_ERROR:' + err.message);
    }

  // Close
  await browser.close();
})();
