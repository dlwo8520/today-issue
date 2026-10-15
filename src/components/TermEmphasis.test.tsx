import { render } from '@testing-library/react';
import { expect, test } from 'vitest';
import { TermEmphasis } from './TermEmphasis';

test('glossary emphasis preserves the complete text, literal symbols and other words', () => {
  const text = 'AI는 AIB와 다르며 C++처럼 기호가 있는 용어도 그대로 읽습니다. AI를 다시 언급합니다.';
  const { container } = render(<p><TermEmphasis text={text} terms={['AI', 'C++']} /></p>);
  expect(container.textContent).toBe(text);
  expect([...container.querySelectorAll('strong')].map(node => node.textContent)).toEqual(['AI', 'C++']);
});
