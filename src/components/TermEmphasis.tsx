export function TermEmphasis({ text, terms }: { text: string; terms: string[] }) {
  const unique = [...new Set(terms.map(term => term.trim()).filter(term => term.length >= 2))]
    .sort((a, b) => b.length - a.length).slice(0, 10);
  if (!unique.length) return <>{text}</>;
  const escape = (term: string) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`(${unique.map(term => /^[\w .()-]+$/.test(term)
    ? `(?<![A-Za-z0-9])${escape(term)}(?![A-Za-z0-9])` : escape(term)).join('|')})`, 'g');
  const highlighted = new Set<string>();
  return <>{text.split(pattern).map((part, index) => {
    if (unique.includes(part) && !highlighted.has(part) && highlighted.size < 3) {
      highlighted.add(part);
      return <strong className="term-emphasis" key={index}>{part}</strong>;
    }
    return part;
  })}</>;
}
