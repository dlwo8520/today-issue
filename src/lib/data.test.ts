import { beforeEach, expect, test, vi } from 'vitest';
import fixture from '../../public/data/demo.json';
import { editionSchema } from '../types/news';
import { formatDate, isStale, loadEdition, loadStatus, publisherCount, windowLabel } from './data';

beforeEach(() => vi.unstubAllGlobals());
test('JSON loads with its mode and schema', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => fixture }));
  expect((await loadEdition('demo')).issues).toHaveLength(6);
});
test('Live never accepts or silently falls back to demo', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => fixture });
  vi.stubGlobal('fetch', fetch);
  await expect(loadEdition('live')).rejects.toThrow('모드');
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toContain('latest.json');
});
test('fetch failures and malformed JSON are rejected', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
  await expect(loadEdition('demo')).rejects.toThrow();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ issues: [] }) }));
  await expect(loadEdition('demo')).rejects.toThrow();
});
test('missing status is optional', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
  expect(await loadStatus()).toBeNull();
});
test('missing evidence IDs and more than six issues rejected', () => {
  const copy = structuredClone(fixture);
  copy.issues[0].summarySourceIds = ['invalid'];
  expect(editionSchema.safeParse(copy).success).toBe(false);
  expect(editionSchema.safeParse({ ...fixture, issues: [...fixture.issues, fixture.issues[0]] }).success).toBe(false);
  const invalidPhoto = { ...fixture, issues: fixture.issues.map(i => ({ ...i,
    sources: i.sources.map(s => ({ ...s, imageUrl: 'https://' })) })) };
  expect(editionSchema.safeParse(invalidPhoto).success).toBe(false);
});
test('KST date and stale live status', () => {
  expect(formatDate('2026-10-13')).toContain('13일');
  const edition = editionSchema.parse(fixture);
  expect(isStale(edition, Date.parse(edition.updatedAt) + 40 * 3600000)).toBe(false);
  expect(isStale({ ...edition, mode: 'live' }, Date.parse(edition.updatedAt) + 365 * 24 * 3600000)).toBe(false);
  expect(windowLabel(edition)).toBe('지난 24시간');
  expect(windowLabel({ ...edition, windowStart: new Date(Date.parse(edition.windowEnd) - 168 * 3600000).toISOString() })).toBe('최근 7일');
  expect(windowLabel({ ...edition, windowStart: new Date(Date.parse(edition.windowEnd) - 336 * 3600000).toISOString() })).toBe('최근 2주');
});
test('API edition preserves provider provenance without counting publisher aliases twice', async () => {
  const issue = structuredClone(fixture.issues[0]);
  const apiIssue = { ...issue, ranking: { ...issue.ranking, method: 'headline_coverage' },
    sources: issue.sources.map((source, index) => ({ ...source, method: 'official_api',
      providers: index === 0 ? ['gnews', 'newsdata'] : ['newsdata'],
      publisher: index === 0 ? '연합뉴스' : 'Yonhap', publisherKey: 'media:yna.co.kr' })) };
  const apiEdition = { ...fixture, mode: 'live', publicationScope: 'local_private',
    rankingMethod: 'headline_coverage', issues: [apiIssue] };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => apiEdition }));
  const loaded = await loadEdition('live');
  expect(loaded.publicationScope).toBe('local_private');
  expect(loaded.issues[0].sources[0].providers).toEqual(['gnews', 'newsdata']);
  expect(publisherCount(loaded.issues[0])).toBe(1);
});
