export function Icon({ name, className = '' }: { name: 'arrow' | 'back' | 'clock' | 'external' | 'book'; className?: string }) {
  const paths = {
    arrow: 'M4 12h16m-6-6 6 6-6 6',
    back: 'M20 12H4m6-6-6 6 6 6',
    clock: 'M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
    external: 'M14 4h6v6m0-6L10 14M10 4H4v16h16v-6',
    book: 'M4 4h16v16H4zM8 8h8M8 12h8M8 16h4',
  };
  return <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
