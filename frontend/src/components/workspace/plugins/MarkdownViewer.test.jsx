import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import MarkdownViewer from './MarkdownViewer';

test('renders workspace markdown title and content', () => {
  render(<MarkdownViewer title="函数资料" content="正文" />);

  expect(screen.getByText('函数资料')).toBeDefined();
  expect(screen.getByRole('heading', { name: '函数资料' })).toBeDefined();
  expect(screen.getByText('正文')).toBeDefined();
});
