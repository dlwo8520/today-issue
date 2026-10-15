import type { Edition } from '../types/news';
import { editionTimeLabel, formatDate, formatTime, windowLabel } from '../lib/data';
import { IssueCard } from '../components/IssueCard';
import { Icon } from '../components/Icon';
export function HomePage({ edition }: { edition: Edition }) {
  return <div className="shell">
    <section className="hero" aria-labelledby="page-title">
      <div><p className="eyebrow"><span />하루를 이해하는 5분</p><h1 id="page-title" tabIndex={-1}>{windowLabel(edition)},<br /><span>어떤 일이 있었을까요?</span></h1><p className="hero-description">흩어진 뉴스를 하나의 이야기로.<br className="mobile-break" /> 꼭 알아둘 이슈만 쉽고 차분하게 전합니다.</p></div>
      <div className="date-block"><span className="date-month">{edition.date.slice(0, 4)}. {edition.date.slice(5, 7)}</span><span className="date-day">{edition.date.slice(8)}</span><span className="date-full">{formatDate(edition.date).split(' ').at(-1)}</span></div>
    </section>
    {edition.mode === 'demo' && <aside className="demo-notice"><span className="notice-label">DEMO</span><p>가상 사건으로 구성한 체험용 에디션입니다. 실제 뉴스와 언론사가 아닙니다.</p></aside>}
    <section className="issues-section" aria-labelledby="issues-title">
      <div className="section-heading"><h2 id="issues-title">{edition.mode === 'demo' ? '오늘의 이슈 미리보기' : '오늘의 주요 보도 이슈'} <span>{String(edition.issues.length).padStart(2, '0')}</span></h2><span className="reading-time"><Icon name="clock" />목표 읽기 시간 약 5분</span></div>
      {edition.issues.length > 0 ? <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 issue-grid">{edition.issues.map(issue => <IssueCard key={issue.id} issue={issue} />)}</div> : <div className="empty-state"><Icon name="book" /><h3>아직 준비된 이슈가 없습니다</h3><p>확인할 수 있는 이슈가 모이면 이곳에 전해드릴게요.</p></div>}
      <div className="edition-meta"><span>{editionTimeLabel(edition)} <time dateTime={edition.updatedAt}>{formatTime(edition.updatedAt)} KST</time></span><span>{windowLabel(edition)} · {edition.mode === 'demo' ? '가상 이슈 미리보기' : '최신 기사 발행 순'}</span></div>
    </section>
    <section className="editorial-note" aria-label="편집 원칙"><span className="note-symbol">“</span><div><h2>많이 읽는 것보다, 잘 이해하는 것.</h2><p>같은 사건은 하나로 모으고, 어려운 말은 풀어서 설명합니다.<br />사실과 주장을 구분하고, 모든 이야기의 출처를 함께 전합니다.</p></div><span className="note-wordmark">LESS NEWS.<br />MORE CONTEXT.</span></section>
  </div>;
}
