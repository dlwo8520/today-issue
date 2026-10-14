import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import fixture from '../public/data/demo.json';
vi.mock('./lib/data', async importOriginal => ({ ...await importOriginal<typeof import('./lib/data')>(), DATA_MODE: 'demo' }));
import App from './App';
import { HomePage } from './pages/HomePage';
import { IssuePage } from './pages/IssuePage';
import { editionSchema } from './types/news';
import { IssueCard } from './components/IssueCard';

const edition = editionSchema.parse(fixture);
beforeEach(() => {
  location.hash = '#/';
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => fixture }));
});
test('renders 6 cards, DEMO and sample update time', async () => {
  const { container } = render(<App />);
  await waitFor(() => expect(container.querySelectorAll('.issue-card')).toHaveLength(6));
  expect(screen.getByText('DEMO 에디션')).toBeInTheDocument();
  expect(screen.getByText('샘플 작성 시각')).toBeInTheDocument();
  expect(screen.getByText(/실제 뉴스와 언론사가 아닙니다/)).toBeInTheDocument();
});
test('loading state appears before JSON resolves', () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})));
  render(<App />);
  expect(screen.getByRole('status')).toHaveAttribute('aria-label', '이슈를 불러오는 중');
});
test('fetch error has retry and recovers', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: false }).mockResolvedValue({ ok: true, json: async () => fixture }));
  render(<App />);
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }));
  expect(await screen.findByText(fixture.issues[0].title)).toBeInTheDocument();
});
test('empty edition explains lack of data', () => {
  render(<HomePage edition={{ ...edition, issues: [] }} />);
  expect(screen.getByText('아직 준비된 이슈가 없습니다')).toBeInTheDocument();
});
test('direct hash URL renders detail with safe source links', async () => {
  location.hash = '#/issue/demo-issue-001';
  const { container } = render(<App />);
  await screen.findByRole('heading', { name: '원문 확인하기' });
  const source = container.querySelector('.source-link');
  expect(source).toHaveAttribute('target', '_blank');
  expect(source).toHaveAttribute('rel', 'noopener noreferrer');
});
test('unknown and malformed hash routes handled', async () => {
  location.hash = '#/issue/%XX';
  render(<App />);
  expect(await screen.findByRole('heading', { name: '이 이슈를 찾을 수 없습니다.' })).toBeInTheDocument();
});
test('unverified reactions and unneeded terminology omitted', () => {
  render(<IssuePage issue={edition.issues[3]} edition={edition} />);
  expect(screen.queryByRole('heading', { name: '어떤 반응이 있나요?' })).not.toBeInTheDocument();
  expect(screen.queryByText('어려운 용어 알아보기')).not.toBeInTheDocument();
});
test('share link can be copied', async () => {
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true });
  render(<IssuePage issue={edition.issues[0]} edition={edition} />);
  fireEvent.click(screen.getByRole('button', { name: /링크 복사/ }));
  expect(await screen.findByText('링크를 복사했습니다.')).toBeInTheDocument();
});
test('clean article keeps original links and navigates through the issue list', async () => {
  const { container } = render(<IssuePage issue={edition.issues[0]} edition={edition} />);
  expect(container.querySelector('.citations')).toBeNull();
  expect(screen.queryByText('이 이슈는 어떻게 선정되었나요?')).not.toBeInTheDocument();
  const list = screen.getByRole('navigation', { name: '이슈 목록' });
  expect(list.querySelectorAll('a')).toHaveLength(6);
  expect(list.querySelector('[aria-current="page"]')).toHaveAttribute('href', '#/issue/demo-issue-001');
  expect(list.querySelectorAll('a')[1]).toHaveAttribute('href', '#/issue/demo-issue-002');
});
test('photo uses the first original source and hides failed images', () => {
  const photoIssue = structuredClone(edition.issues[0]);
  photoIssue.sources[0].imageUrl = 'https://news.example.com/first.jpg';
  photoIssue.sources[1].imageUrl = 'https://news.example.com/second.jpg';
  const { container } = render(<IssueCard issue={photoIssue} />);
  const image = container.querySelector('img')!;
  expect(image).toHaveAttribute('src', 'https://news.example.com/first.jpg');
  fireEvent.error(image);
  expect(container.querySelector('figure')).toBeNull();
});
