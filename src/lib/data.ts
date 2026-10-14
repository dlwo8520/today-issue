import { editionSchema, statusSchema, type Edition, type UpdateStatus } from '../types/news';

export type DataMode = 'demo' | 'live';
export const DATA_MODE: DataMode = import.meta.env.VITE_DATA_MODE === 'live' ? 'live' : 'demo';
export async function loadEdition(mode: DataMode, signal?: AbortSignal): Promise<Edition> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${mode === 'demo' ? 'demo' : 'latest'}.json`, { signal, cache: 'no-cache' });
  if (!response.ok) throw new Error('뉴스 데이터를 불러오지 못했습니다.');
  const edition = editionSchema.parse(await response.json());
  if (edition.mode !== mode) throw new Error('데이터 모드가 일치하지 않습니다.');
  return edition;
}
export async function loadStatus(signal?: AbortSignal): Promise<UpdateStatus | null> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/status.json`, { signal, cache: 'no-cache' });
  if (!response.ok) return null;
  return statusSchema.parse(await response.json());
}
export const formatDate = (date: string) => new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul', year: 'numeric', month: 'long', day: 'numeric', weekday: 'long',
}).format(new Date(`${date}T12:00:00+09:00`));
export const formatTime = (date: string) => new Intl.DateTimeFormat('ko-KR', {
  timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
}).format(new Date(date));
export const isStale = (edition: Edition, now = Date.now()) => edition.mode === 'live' && now - Date.parse(edition.updatedAt) > 30 * 60 * 60 * 1000;
export const publisherCount = (issue: Edition['issues'][number]) => new Set(issue.sources.map(s => s.publisherKey || s.publisher)).size;
export const windowLabel = (edition: Edition) => {
  const hours = (Date.parse(edition.windowEnd) - Date.parse(edition.windowStart)) / 3600000;
  return Math.abs(hours - 336) < 0.01 ? '최근 2주' : Math.abs(hours - 168) < 0.01 ? '최근 7일' : Math.abs(hours - 24) < 0.01 ? '지난 24시간' : `최근 ${Math.round(hours / 24)}일`;
};
