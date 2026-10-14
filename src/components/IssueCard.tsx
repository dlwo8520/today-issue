import type { Issue } from '../types/news';
import { publisherCount } from '../lib/data';
import { Icon } from './Icon';
import { ArticlePhoto } from './ArticlePhoto';
export function IssueCard({ issue }: { issue: Issue }) {
  return <a className="issue-card" href={`#/issue/${encodeURIComponent(issue.id)}`}>
    <ArticlePhoto issue={issue} />
    <div className="card-top"><span className="issue-number">{String(issue.rank).padStart(2, '0')}</span><span className="card-kicker">TODAY’S ISSUE</span></div>
    <h3>{issue.title}</h3>
    <p>{issue.oneLineSummary}</p>
    <div className="card-bottom"><span>관련 언론사 <strong>{publisherCount(issue)}곳</strong></span><span className="card-action">자세히 읽기 <Icon name="arrow" /></span></div>
  </a>;
}
