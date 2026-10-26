import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi, beforeEach } from 'vitest';
import MarkdownViewer from './MarkdownViewer';
import apiClient from '../../../api/client';

vi.mock('../../../context/ChatContext', () => ({
  useChat: () => ({ activeSession: 'conversation-1' })
}));

vi.mock('../../../api/client', () => ({
  default: {
    get: vi.fn(),
  }
}));

beforeEach(() => {
  vi.clearAllMocks();
  globalThis.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
  globalThis.URL.revokeObjectURL = vi.fn();
});

test('renders workspace markdown title and content', () => {
  render(<MarkdownViewer title="函数资料" content="正文" />);

  expect(screen.getByText('函数资料')).toBeDefined();
  expect(screen.getByRole('heading', { name: '函数资料' })).toBeDefined();
  expect(screen.getByText('正文')).toBeDefined();
});

test('renders heading anchors and conversation artifact downloads', async () => {
  const fakeBlob = new Blob(['# 讲义'], { type: 'text/markdown' });
  apiClient.get.mockResolvedValue(fakeBlob);

  render(
    <MarkdownViewer
      content={'[外链](https://example.com)\n\n[目录](#第一章)\n\n# 第一章\n\n[下载讲义](./讲义.md)'}
    />
  );

  // 验证标题 id
  expect(screen.getByRole('heading', { name: '第一章' })).toHaveAttribute('id', '第一章');

  // 验证普通外链
  const extLink = screen.getByRole('link', { name: '外链' });
  expect(extLink).toHaveAttribute('href', 'https://example.com');
  expect(extLink).toHaveAttribute('target', '_blank');
  expect(extLink).toHaveAttribute('rel', 'noopener noreferrer');

  // 验证锚点链接
  const anchorLink = screen.getByRole('link', { name: '目录' });
  expect(decodeURIComponent(anchorLink.getAttribute('href'))).toBe('#第一章');
  expect(anchorLink).not.toHaveAttribute('target');

  // 验证下载链接与点击调用
  const downloadLink = screen.getByRole('link', { name: /下载讲义/ });
  expect(downloadLink).toHaveAttribute(
    'href',
    expect.stringContaining('/tutoring/conversations/conversation-1/files/')
  );
  expect(downloadLink.getAttribute('href')).not.toContain('token=');

  fireEvent.click(downloadLink);

  await waitFor(() => {
    expect(apiClient.get).toHaveBeenCalledWith(
      '/tutoring/conversations/conversation-1/files/%E8%AE%B2%E4%B9%89.md',
      { responseType: 'blob' }
    );
  });

  expect(globalThis.URL.createObjectURL).toHaveBeenCalledWith(fakeBlob);
  expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
});
