import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import AgentWorkspace from './AgentWorkspace';
import { useChat } from '../../context/ChatContext';

// Mock useChat hook
vi.mock('../../context/ChatContext', () => ({
  useChat: vi.fn(),
}));

// Mock PluginRegistry to isolate AgentWorkspace testing
vi.mock('./PluginRegistry', () => ({
  PluginRegistry: {
    QuizCard: ({ question }) => <div data-testid="quiz-card">{question}</div>,
    Markdown: ({ title, content }) => (
      <article data-testid="markdown-artifact">
        <h1>{title}</h1>
        <div>{content}</div>
      </article>
    ),
  },
}));

test('renders empty state when no artifacts exist', () => {
  useChat.mockReturnValue({ workspaceArtifacts: [] });
  render(<AgentWorkspace />);
  expect(screen.getByText(/暂无生成产物/)).toBeDefined();
});

test('renders plugin components when artifacts exist', () => {
  useChat.mockReturnValue({
    workspaceArtifacts: [
      { id: '1', type: 'QuizCard', props: { question: 'What is React?' } },
    ],
  });
  render(<AgentWorkspace />);
  expect(screen.getByTestId('quiz-card')).toBeDefined();
  expect(screen.getByText('What is React?')).toBeDefined();
});

test('renders markdown artifact title and content', () => {
  useChat.mockReturnValue({
    workspaceArtifacts: [
      {
        id: 'artifact_001_functions',
        type: 'Markdown',
        props: { title: '函数资料', content: '# 函数资料' },
      },
    ],
  });

  render(<AgentWorkspace />);

  expect(screen.getByTestId('markdown-artifact')).toBeDefined();
  expect(screen.getByText('函数资料')).toBeDefined();
  expect(screen.getByText('# 函数资料')).toBeDefined();
});

test('renders error message for unknown plugin type', () => {
  useChat.mockReturnValue({
    workspaceArtifacts: [
      { id: '2', type: 'UnknownType', props: {} },
    ],
  });
  render(<AgentWorkspace />);
  expect(screen.getByText(/未知插件类型: UnknownType/)).toBeDefined();
});
