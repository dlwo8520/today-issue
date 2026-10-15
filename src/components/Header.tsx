import { Icon } from './Icon';
export function Header({ demo, frozen = false }: { demo: boolean; frozen?: boolean }) {
  return <header className="site-header"><div className="shell header-inner">
    <a className="brand" href="#/" aria-label="오늘의 잇슈 홈"><span className="brand-mark"><Icon name="book" /></span>오늘의 잇슈<span className="brand-dot">.</span></a>
    <div className="header-note"><span className="edition-label">TODAY’S ISSUE</span><span className="mode-tag">{demo ? 'DEMO 에디션' : frozen ? '고정 에디션' : 'DAILY EDITION'}</span></div>
  </div></header>;
}
