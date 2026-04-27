const { test, expect } = require('@playwright/test');

test('admin can insert and delete internal consignment row', async ({ page }) => {
  const adminUsername = process.env.ADMIN_USERNAME || 'admin';
  const adminPassword = process.env.ADMIN_E2E_PASSWORD;

  if (!adminPassword) {
    test.skip(true, 'ADMIN_E2E_PASSWORD is required for admin UI insert/delete test');
  }

  const consignmentNumber = `UI${Date.now()}`;

  await page.goto('/admin/login');
  await page.locator('#username').fill(adminUsername);
  await page.locator('#password').fill(adminPassword);
  await page.getByRole('button', { name: /sign in/i }).click();

  await expect(page).toHaveURL(/\/admin\/dashboard/);

  await page.goto('/admin/consignments');
  await page.getByRole('button', { name: /add row/i }).click();

  const row = page.locator('#sheet-body tr').last();
  await row.locator('input.consignment_number').fill(consignmentNumber);
  await row.locator('select.status').selectOption('In Transit');
  await row.locator('input.pickup_pincode').fill('110017');
  await row.locator('input.drop_pincode').fill('400001');

  await page.getByRole('button', { name: /save all/i }).click();
  await expect(page.locator('#status-msg')).toContainText(/saved successfully/i, { timeout: 120000 });
  await page.waitForLoadState('networkidle');

  await expect(page.locator(`input.consignment_number[value="${consignmentNumber}"]`)).toHaveCount(1, {
    timeout: 120000,
  });

  const insertedRow = page.locator('#sheet-body tr', {
    has: page.locator(`input.consignment_number[value="${consignmentNumber}"]`),
  }).first();

  await insertedRow.getByRole('button', { name: /delete/i }).click();
  await page.getByRole('button', { name: /save all/i }).click();
  await expect(page.locator('#status-msg')).toContainText(/saved successfully/i, { timeout: 120000 });
  await page.waitForLoadState('networkidle');

  await expect(page.locator(`input.consignment_number[value="${consignmentNumber}"]`)).toHaveCount(0, {
    timeout: 120000,
  });
});
