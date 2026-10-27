import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi, beforeEach } from 'vitest';
import MarkdownViewer from './MarkdownViewer';
import apiClient from '../../api/client';

vi.mock('../../context/ChatContext', () => ({
  useChat: () => ({ activeSession: 'conversation-1' })
}));

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
  }
}));

vi.mock('../../utils/mermaid', () => ({
  default: {
    render: vi.fn().mockResolvedValue({
      svg: '<svg width="100%" viewBox="0 0 2400 1200"><text>测试图解</text></svg>'
    })
  },
  sanitizeMermaidSource: (source) => source.trim(),
  getCachedSvg: () => undefined,
  setCachedSvg: vi.fn()
}));

beforeEach(() => {
  vi.clearAllMocks();
  globalThis.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
  globalThis.URL.revokeObjectURL = vi.fn();
});

test('fits Mermaid diagrams by default and allows original-size viewing', async () => {
  render(<MarkdownViewer content={'```mermaid\ngraph TD\nA --> B\n```'} />);

  const viewport = await screen.findByTestId('mermaid-viewport');
  await waitFor(() => expect(viewport.querySelector('svg')).not.toBeNull());

  expect(viewport).toHaveAttribute('data-view-mode', 'fit');
  expect(screen.getByRole('button', { name: '适应窗口' })).toHaveAttribute('aria-pressed', 'true');

  fireEvent.click(screen.getByRole('button', { name: '原始大小' }));

  expect(viewport).toHaveAttribute('data-view-mode', 'original');
  expect(screen.getByRole('button', { name: '原始大小' })).toHaveAttribute('aria-pressed', 'true');
});

test('handles artifact download via apiClient blob response and preserves link behaviors', async () => {
  const fakeBlob = new Blob(['# 讲义内容'], { type: 'text/markdown' });
  apiClient.get.mockResolvedValue(fakeBlob);

  render(
    <MarkdownViewer
      content={'[外链](https://example.com)\n\n[目录](#第一章)\n\n# 第一章\n\n[下载讲义](./讲义.md)'}
    />
  );

  // 验证普通外链
  const extLink = screen.getByRole('link', { name: '外链' });
  expect(extLink).toHaveAttribute('href', 'https://example.com');
  expect(extLink).toHaveAttribute('target', '_blank');
  expect(extLink).toHaveAttribute('rel', 'noopener noreferrer');

  // 验证锚点链接
  const anchorLink = screen.getByRole('link', { name: '目录' });
  expect(decodeURIComponent(anchorLink.getAttribute('href'))).toBe('#第一章');
  expect(anchorLink).not.toHaveAttribute('target');

  // 验证对话文件下载链接
  const downloadLink = screen.getByRole('link', { name: /下载讲义/ });
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

test('renders fenced code blocks without language annotation as block-level code container', () => {
  const content = '```\n1\n7\n```';
  const { container } = render(<MarkdownViewer content={content} />);

  // 必须渲染带有头部和复制按钮的标准代码块容器
  expect(screen.getByText('code')).toBeDefined();
  expect(screen.getByRole('button', { name: /Copy/i })).toBeDefined();
  expect(container.textContent).toContain('1');
  expect(container.textContent).toContain('7');

  // 确保没有 fallback 渲染成行内药丸标签
  const inlineCodes = container.querySelectorAll('code.bg-slate-100.text-cyan-700');
  expect(inlineCodes.length).toBe(0);
});

test('renders inline code with backticks as inline code tag without block container', () => {
  const content = '这是行内代码 `variable_name` 测试';
  const { container } = render(<MarkdownViewer content={content} />);

  expect(screen.queryByRole('button', { name: /Copy/i })).toBeNull();
  const inlineCode = container.querySelector('code.bg-slate-100');
  expect(inlineCode).not.toBeNull();
  expect(inlineCode.textContent).toBe('variable_name');
});
