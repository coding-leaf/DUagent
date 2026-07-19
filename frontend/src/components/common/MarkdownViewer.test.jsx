import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import MarkdownViewer from './MarkdownViewer';

vi.mock('../../context/ChatContext', () => ({
  useChat: () => ({ activeSession: 'conversation-1' })
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
