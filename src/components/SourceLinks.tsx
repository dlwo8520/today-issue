import type { Issue } from '../types/news';
import { Icon } from './Icon';
export function SourceLinks({ sources, demo }: { sources: Issue['sources']; demo: boolean }) {
  return <div className="source-list">{sources.map((source, index) => <a key={source.id} id={`source-${source.id}`} href={source.url} target="_blank" rel="noopener noreferrer" className="source-link">
    <span className="source-index">{String(index + 1).padStart(2, '0')}</span><span><strong>{source.publisher}</strong><span className="source-title">{source.title}</span></span><span className="source-open">{demo ? '샘플 링크' : '원문 보기'}<Icon name="external" /></span>
  </a>)}</div>;
}
