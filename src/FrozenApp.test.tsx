import { render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import fixture from '../public/data/demo.json';
vi.mock('./lib/data', async importOriginal => ({ ...await importOriginal<typeof import('./lib/data')>(), DATA_MODE: 'live' }));
import App from './App';

test('frozen edition loads only saved articles and never shows delayed-update warnings', async () => {
  location.hash = '#/';
  const live = { ...fixture, mode: 'live', rankingMethod: 'coverage_recency',
    issues: fixture.issues.map(issue => ({ ...issue, ranking: { ...issue.ranking, method: 'coverage_recency' },
      sources: issue.sources.map(source => ({ ...source, method: 'rss' })) })) };
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => live });
  vi.stubGlobal('fetch', fetch);
  const { container } = render(<App />);
  await waitFor(() => expect(container.querySelectorAll('.issue-card')).toHaveLength(6));
  expect(screen.getByText('고정 에디션')).toBeInTheDocument();
  expect(screen.getByText('고정 기준 시각')).toBeInTheDocument();
  expect(container.querySelector('.update-warning')).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toContain('data/latest.json');
});
