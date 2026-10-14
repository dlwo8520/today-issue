import { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { HomePage } from './pages/HomePage';
import { IssuePage } from './pages/IssuePage';
import { DATA_MODE, isStale, loadEdition, loadStatus } from './lib/data';
import type { Edition, UpdateStatus } from './types/news';

export default function App() {
  const [edition, setEdition] = useState<Edition | null>(null);
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [route, setRoute] = useState(location.hash || '#/');
  useEffect(() => { const onHash = () => setRoute(location.hash || '#/'); window.addEventListener('hashchange', onHash); return () => window.removeEventListener('hashchange', onHash); }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError(false); setEdition(null); setStatus(null);
    loadEdition(DATA_MODE, controller.signal).then(setEdition).catch(e => { if (e.name !== 'AbortError') setError(true); });
    if (DATA_MODE === 'live') loadStatus(controller.signal).then(setStatus).catch(() => {});
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => { window.scrollTo(0, 0); document.getElementById('page-title')?.focus({ preventScroll: true }); }, [route, edition]);
  let id: string | null = null;
  try { const match = /^#\/issue\/([^/]+)$/.exec(route); id = match ? decodeURIComponent(match[1]) : null; } catch { /* invalid URL renders not-found */ }
  const issue = edition?.issues.find(item => item.id === id);
  const isHome = route === '#/' || route === '' || route === '#';
  useEffect(() => { document.title = `${issue?.title ?? '하루를 이해하는 5분'} · 오늘의 잇슈`; }, [issue]);
  return <><a className="skip-link" href="#main-content" onClick={e => { e.preventDefault(); document.getElementById('main-content')?.focus(); }}>본문으로 건너뛰기</a><Header demo={DATA_MODE === 'demo'} /><main id="main-content" tabIndex={-1}>
    {error ? <div className="shell state-panel" role="alert"><p className="eyebrow">잠시 쉬어가는 중</p><h1 id="page-title">이슈를 불러오지 못했습니다.</h1><p>데이터 연결을 확인하고 다시 시도해 주세요.{DATA_MODE === 'live' && ' 이전 정상 데이터가 없거나 읽을 수 없는 상태입니다.'}</p><button className="primary-button" onClick={() => setAttempt(n => n + 1)}>다시 불러오기</button></div> : !edition ? <div className="shell loading-state" role="status" aria-label="이슈를 불러오는 중"><div className="skeleton hero-skeleton" /><div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton card-skeleton" />)}</div><span className="sr-only">이슈를 불러오는 중입니다.</span></div> : <>
      {(isStale(edition) || (status?.state === 'error' && Date.parse(status.attemptedAt) >= Date.parse(edition.updatedAt))) && <div className="shell update-warning" role="status">최근 업데이트가 지연되었습니다. 마지막으로 정상 생성된 에디션을 보여드립니다. 아래 업데이트 시각을 확인해 주세요.</div>}
      {isHome ? <HomePage edition={edition} /> : issue ? <IssuePage key={issue.id} issue={issue} edition={edition} /> : <div className="shell state-panel"><h1 id="page-title">이 이슈를 찾을 수 없습니다.</h1><p>현재 에디션에 없는 이슈입니다. 오늘의 목록에서 다시 확인해 주세요.</p><a href="#/" className="primary-button">오늘의 이슈 보기</a></div>}
    </>}
  </main><footer className="site-footer shell"><a className="footer-brand" href="#/">오늘의 잇슈<span>.</span></a><p>하루 한 번, 세상을 조금 더 가깝게.</p><span>© {new Date().getFullYear()} TODAY’S ISSUE</span></footer></>;
}
