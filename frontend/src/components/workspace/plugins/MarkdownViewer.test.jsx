import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import MarkdownViewer from './MarkdownViewer';

vi.mock('../../../context/ChatContext', () => ({
  useChat: () => ({ activeSession: 'conversation-1' })
}));

test('renders workspace markdown title and content', () => {
  render(<MarkdownViewer title="函数资料" content="正文" />);

  expect(screen.getByText('函数资料')).toBeDefined();
  expect(screen.getByRole('heading', { name: '函数资料' })).toBeDefined();
  expect(screen.getByText('正文')).toBeDefined();
});

test('renders heading anchors and conversation artifact downloads', () => {
  render(
    <MarkdownViewer
      content={'[目录](#第一章)\n\n# 第一章\n\n[下载讲义](./讲义.md)'}
    />
  );

  expect(screen.getByRole('heading', { name: '第一章' })).toHaveAttribute('id', '第一章');
  expect(screen.getByRole('link', { name: '目录' })).not.toHaveAttribute('target');
  expect(screen.getByRole('link', { name: /下载讲义/ })).toHaveAttribute(
    'href',
    expect.stringContaining('/tutoring/conversations/conversation-1/files/')
  );
});
