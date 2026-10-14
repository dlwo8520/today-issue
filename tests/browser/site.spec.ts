import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

for (const [name, width, columns] of [['desktop', 1440, 3], ['tablet', 800, 2], ['mobile', 390, 1]] as const) {
  test(`${name}: layout, sources, direct refresh, accessibility`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('./');
    const cards = page.locator('.issue-card');
    await expect(cards).toHaveCount(6);
    const count = await page.locator('.issue-grid').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
    expect(count).toBe(columns);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `docs/screenshots/${name}-home.png`, fullPage: true });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await cards.first().click();
    await expect(page).toHaveURL(/#\/issue\/demo-issue-001$/);
    await expect(page.getByRole('heading', { name: '지금은 어떤 상황인가요?' })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: '원문 확인하기' })).toBeVisible();
    await expect(page.locator('.citations, .ranking-details')).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: '이슈 목록' }).locator('a')).toHaveCount(6);
    await expect(page.locator('.source-link').first()).toHaveAttribute('rel', 'noopener noreferrer');
    await expect(page.locator('.source-link').first()).toHaveAttribute('target', '_blank');
    await page.screenshot({ path: `docs/screenshots/${name}-detail.png`, fullPage: true });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.getByRole('navigation', { name: '이슈 목록' }).locator('a').nth(1).click();
    await expect(page).toHaveURL(/#\/issue\/demo-issue-002$/);
    await expect(page.getByRole('navigation', { name: '이슈 목록' }).locator('[aria-current="page"]')).toContainText('02');
  });
}
test('keyboard and error recovery', async ({ page }) => {
  let fail = true;
  await page.route('**/data/demo.json', route => fail ? route.fulfill({ status: 503 }) : route.continue());
  await page.goto('./');
  await expect(page.getByRole('alert')).toBeVisible();
  fail = false;
  await page.getByRole('button', { name: '다시 불러오기' }).click();
  await expect(page.locator('.issue-card')).toHaveCount(6);
  await page.locator('.issue-card').first().focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/demo-issue-001/);
});
test('missing issue and malformed data', async ({ page }) => {
  await page.goto('./#/issue/missing');
  await expect(page.getByRole('heading', { name: '이 이슈를 찾을 수 없습니다.' })).toBeVisible();
  await page.route('**/data/demo.json', route => route.fulfill({ json: { issues: [] } }));
  await page.reload();
  await expect(page.getByRole('alert')).toBeVisible();
});
