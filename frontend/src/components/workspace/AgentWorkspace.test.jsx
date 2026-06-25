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

test('renders error message for unknown plugin type', () => {
  useChat.mockReturnValue({
    workspaceArtifacts: [
      { id: '2', type: 'UnknownType', props: {} },
    ],
  });
  render(<AgentWorkspace />);
  expect(screen.getByText(/未知插件类型: UnknownType/)).toBeDefined();
});
