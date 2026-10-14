import { useState } from 'react';
import type { Issue } from '../types/news';

export function ArticlePhoto({ issue, detail = false }: { issue: Issue; detail?: boolean }) {
  const source = issue.sources[0];
  const [failed, setFailed] = useState(false);
  if (!source?.imageUrl || failed) return null;
  return <figure className={detail ? 'article-photo' : 'card-photo'}>
    <img src={source.imageUrl} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
    <figcaption>사진 출처 · {source.publisher}</figcaption>
  </figure>;
}
