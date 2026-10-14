import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';

test.skip(!process.env.TEST_REAL_LIVE, 'Opt-in local private Live verification only');
test('real Live JSON renders with sources, no DEMO, and working direct URLs', async ({ page }) => {
  const edition = JSON.parse(readFileSync('public/data/latest.json', 'utf8'));
  expect(edition.mode).toBe('live');
  expect(edition.publicationScope).toBe('local_private');
  const articleTimes = edition.issues.map((issue: { sources: { publishedAt: string }[] }) => Math.max(...issue.sources.map(source => Date.parse(source.publishedAt))));
  expect(articleTimes).toEqual([...articleTimes].sort((a, b) => b - a));
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('./');
    await expect(page.locator('.issue-card')).toHaveCount(edition.issues.length);
    await expect(page.getByText('DEMO 에디션')).toHaveCount(0);
    await expect(page.getByText('마지막 업데이트')).toBeVisible();
    if (Date.parse(edition.windowEnd) - Date.parse(edition.windowStart) === 168 * 3600000) {
      await expect(page.locator('#page-title')).toContainText('최근 7일');
    }
    if (Date.parse(edition.windowEnd) - Date.parse(edition.windowStart) === 336 * 3600000) {
      await expect(page.locator('#page-title')).toContainText('최근 2주');
    }
    await expect(page.locator('.mobile-date, .update-warning')).toHaveCount(0);
    await expect(page.locator('.issue-card').first()).toContainText(edition.issues[0].title);
    const photos = page.locator('.card-photo img');
    await expect(photos).toHaveCount(edition.issues.filter((issue: { sources: { imageUrl?: string }[] }) => issue.sources[0].imageUrl).length);
    for (const photo of await photos.all()) {
      await photo.scrollIntoViewIfNeeded();
      await expect.poll(() => photo.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: `data/reports/screenshots/live-${width}-home.png`, fullPage: true });
    await page.locator('.issue-card').first().click();
    await page.reload();
    await expect(page.getByRole('heading', { name: '원문 확인하기' })).toBeVisible();
    await expect(page.locator('.citations, .ranking-details')).toHaveCount(0);
    const issueList = page.getByRole('navigation', { name: '이슈 목록' });
    await expect(issueList.locator('a')).toHaveCount(edition.issues.length);
    if (width === 1440) {
      const articleBox = await page.locator('.reading-shell').boundingBox();
      const listBox = await issueList.boundingBox();
      expect(listBox!.x).toBeGreaterThan(articleBox!.x + articleBox!.width);
    }
    await expect(page.locator('.source-link')).toHaveCount(edition.issues[0].sources.length);
    await expect(page.locator('.source-link').first()).toHaveAttribute('href', edition.issues[0].sources[0].url);
    await expect(page.locator('.source-link').first()).toHaveAttribute('target', '_blank');
    await expect(page.locator('.source-link').first()).toHaveAttribute('rel', 'noopener noreferrer');
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: `data/reports/screenshots/live-${width}-detail.png`, fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (edition.issues.length > 1) {
      await issueList.locator('a').nth(1).click();
      await expect(page.locator('#page-title')).toHaveText(edition.issues[1].title);
    }
  }
  expect(errors).toEqual([]);
});
