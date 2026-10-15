import { useState } from 'react';
import type { Edition, Issue, Statement } from '../types/news';
import { formatTime, publisherCount } from '../lib/data';
import { Icon } from '../components/Icon';
import { SourceLinks } from '../components/SourceLinks';
import { ArticlePhoto } from '../components/ArticlePhoto';
import { TermEmphasis } from '../components/TermEmphasis';

function ReadingSection({ title, statements, terms }: { title: string; statements: Statement[]; terms: string[] }) {
  if (!statements.length) return null;
  return <section className="reading-section"><h2>{title}</h2><div className="statement-stack">{statements.map(statement =>
    <div key={statement.id} className={statement.kind === 'claim' ? 'statement statement-claim' : 'statement'}>
      {statement.kind === 'claim' && <div className="claim-meta"><span className="claim-tag">주장</span><span>{statement.attribution}</span></div>}
      <p><TermEmphasis text={statement.text} terms={terms} /></p>
    </div>)}</div></section>;
}
export function IssuePage({ issue, edition }: { issue: Issue; edition: Edition }) {
  const [copyStatus, setCopyStatus] = useState('');
  const terms = issue.terminology.map(item => item.term);
  async function copyLink() {
    try { await navigator.clipboard.writeText(location.href); setCopyStatus('링크를 복사했습니다.'); }
    catch { setCopyStatus('주소창의 URL을 복사해 공유할 수 있습니다.'); }
  }
  return <div className="detail-layout shell"><article className="reading-shell">
    <a href="#/" className="back-link"><Icon name="back" />오늘의 이슈로 돌아가기</a>
    <header className="article-header"><p className="eyebrow">ISSUE {String(issue.rank).padStart(2, '0')}<span className="article-meta">관련 언론사 {publisherCount(issue)}곳{edition.mode === 'demo' && ' · DEMO'}</span></p><h1 id="page-title" tabIndex={-1}>{issue.title}</h1><div className="article-summary"><span className="summary-label">한눈에 보는 이슈</span><p className="article-lead"><TermEmphasis text={issue.oneLineSummary} terms={terms} /></p></div></header>
    <ArticlePhoto issue={issue} detail />
    {edition.mode === 'demo' && <aside className="demo-notice detail-demo"><span className="notice-label">DEMO</span><p>이 사건과 언론사는 가상입니다. 원문 예시는 example.com으로 연결됩니다.</p></aside>}
    <ReadingSection title="어떤 배경이 있나요?" statements={issue.background} terms={terms} />
    <ReadingSection title="지금은 어떤 상황인가요?" statements={issue.currentSituation} terms={terms} />
    <ReadingSection title="어떤 반응이 있나요?" statements={issue.response} terms={terms} />
    {issue.terminology.length > 0 && <section className="terminology"><h2><Icon name="book" />어려운 용어 알아보기</h2><dl>{issue.terminology.map(term => <div key={term.term}><dt>{term.term}</dt><dd>{term.explanation}</dd></div>)}</dl></section>}
    <section className="reading-section sources-section"><h2>원문 확인하기</h2><p className="section-description">{edition.mode === 'demo' ? '출처 링크의 구성을 보여주는 가상 기사입니다.' : '서로 다른 보도를 직접 읽고 맥락을 확인해 보세요.'}</p><SourceLinks sources={issue.sources} demo={edition.mode === 'demo'} /></section>
    <p className="small-note">{edition.mode === 'demo' ? '샘플 작성 시각' : '마지막 업데이트'} {formatTime(edition.updatedAt)} KST</p><div className="article-bottom"><a href="#/" className="back-link"><Icon name="back" />목록으로 돌아가기</a><button onClick={copyLink} className="copy-button">링크 복사 <Icon name="external" /></button></div><p className="copy-status" role="status">{copyStatus}</p>
  </article><nav className="issue-sidebar" aria-label="이슈 목록">
    <h2>이슈 목록 <span>{String(edition.issues.length).padStart(2, '0')}</span></h2>
    <ol>{edition.issues.map(item => <li key={item.id}><a href={`#/issue/${encodeURIComponent(item.id)}`} aria-current={item.id === issue.id ? 'page' : undefined}>
      <span className="sidebar-number">{String(item.rank).padStart(2, '0')}</span><span>{item.title}</span>
    </a></li>)}</ol>
  </nav></div>;
}
