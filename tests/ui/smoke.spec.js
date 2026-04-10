const { test, expect } = require('@playwright/test');

test('home page loads primary messaging', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.hero-section h1')).toContainText(/Integrated Logistics/i);
  await expect(page.getByRole('link', { name: /Learn More/i })).toBeVisible();
});

test('home page does not horizontally overflow on mobile', async ({ page }) => {
  await page.goto('/');

  const viewportWidth = page.viewportSize()?.width;
  expect(viewportWidth).toBeTruthy();

  const overflowWidth = await page.evaluate(() => {
    const documentElement = document.documentElement;
    return Math.max(documentElement.scrollWidth, document.body.scrollWidth);
  });

  expect(overflowWidth).toBeLessThanOrEqual(viewportWidth + 1);
});

test('home page sections span edge to edge', async ({ page }) => {
  await page.goto('/');

  for (const selector of ['#services', '#intro', '#about']) {
    const section = page.locator(selector).first();
    await expect(section).toBeVisible();

    const box = await section.boundingBox();
    const viewport = page.viewportSize();

    expect(box).not.toBeNull();
    expect(viewport).not.toBeNull();

    expect(Math.abs(box.x)).toBeLessThanOrEqual(1);
    expect(Math.abs(box.width - viewport.width)).toBeLessThanOrEqual(2);
  }
});

test('home intro section uses neutral background', async ({ page }) => {
  await page.goto('/');

  const intro = page.locator('#intro');
  await expect(intro).toBeVisible();

  const backgroundColor = await intro.evaluate((element) => getComputedStyle(element).backgroundColor);
  expect(backgroundColor).toBe('rgb(255, 255, 255)');
});

test('track page renders shipment form', async ({ page }) => {
  await page.goto('/track');
  await expect(page.getByRole('heading', { level: 1, name: /Track Your Shipment/i })).toBeVisible();
  await expect(page.getByPlaceholder(/Enter Consignment Number/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /Track Shipment/i })).toBeVisible();
});

test('tracker tooltip stays within viewport bounds', async ({ page }) => {
  await page.goto('/track');
  await page.getByPlaceholder(/Enter Consignment Number/i).fill('HOME123');
  await page.getByRole('button', { name: /Track Shipment/i }).click();

  const status = page.locator('.track-status');
  await expect(status).toBeVisible();
  await status.click();

  const tooltip = page.locator('#deliveryTracker');
  await expect(tooltip).toHaveClass(/active/);

  const bounds = await tooltip.boundingBox();
  expect(bounds).not.toBeNull();

  const viewport = page.viewportSize();
  expect(viewport).not.toBeNull();

  const margin = 16;
  expect(bounds.x).toBeGreaterThanOrEqual(margin - 1);
  expect(bounds.y).toBeGreaterThanOrEqual(margin - 1);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width - margin + 1);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height - margin + 1);
});

test('contact page renders form controls', async ({ page }) => {
  await page.goto('/contact');
  await expect(page.getByRole('heading', { level: 1, name: /Contact Us/i })).toBeVisible();
  await expect(page.locator('#name')).toBeVisible();
  await expect(page.locator('#email')).toBeVisible();
  await expect(page.locator('#message')).toBeVisible();
  await expect(page.getByRole('button', { name: /Send Message/i })).toBeVisible();
});
