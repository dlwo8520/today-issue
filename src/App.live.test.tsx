import { render, screen } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import fixture from '../public/data/demo.json';
vi.mock('./lib/data', async importOriginal => ({ ...await importOriginal<typeof import('./lib/data')>(), DATA_MODE: 'live' }));
import App from './App';

const live = { ...fixture, mode: 'live', rankingMethod: 'coverage_recency',
  updatedAt: new Date().toISOString(),
  issues: fixture.issues.map(i => ({ ...i, sources: i.sources.map(s => ({ ...s, method: 'rss' })), ranking: { ...i.ranking, method: 'coverage_recency' } })) };
beforeEach(() => { location.hash = '#/'; });
test('failed update displays last edition and explicit warning', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve({ ok: true,
    json: async () => url.includes('status') ? { attemptedAt: new Date(Date.now() + 1000).toISOString(), state: 'error', message: 'failed' } : live })));
  render(<App />);
  expect(await screen.findByText(/최근 업데이트가 지연되었습니다/)).toBeInTheDocument();
  expect(await screen.findByText(fixture.issues[0].title)).toBeInTheDocument();
  expect(screen.getByText('마지막 업데이트')).toBeInTheDocument();
  expect(screen.queryByText('DEMO 에디션')).not.toBeInTheDocument();
});
test('unavailable optional status does not hide a fresh edition', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve({ ok: !url.includes('status'), json: async () => live })));
  render(<App />);
  expect(await screen.findByText(fixture.issues[0].title)).toBeInTheDocument();
  expect(screen.queryByText(/최근 업데이트가 지연되었습니다/)).not.toBeInTheDocument();
});
test('first Live update without prior JSON shows an error instead of demo', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
  render(<App />);
  await screen.findByRole('alert');
  expect(screen.queryByText(fixture.issues[0].title)).not.toBeInTheDocument();
  expect(screen.queryByText('DEMO 에디션')).not.toBeInTheDocument();
});
