import { render, screen, fireEvent } from '@testing-library/react';
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
  // Expect two occurrences: one in the tab button, one in the markdown content
  expect(screen.getAllByText('函数资料')).toHaveLength(2);
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

test('renders tabs and handles tab click', () => {
  const setActiveArtifactIdMock = vi.fn();
  useChat.mockReturnValue({
    workspaceArtifacts: [
      { id: 'art1', type: 'QuizCard', props: { question: 'Q1' }, title: 'Tab 1' },
      { id: 'art2', type: 'Markdown', props: { title: 'T2', content: 'C2' }, title: 'Tab 2' },
    ],
    activeArtifactId: 'art1',
    setActiveArtifactId: setActiveArtifactIdMock,
  });

  render(<AgentWorkspace />);
  
  // Search for the button using 'T2' because props.title is now preferred
  const tab2 = screen.getByText('T2');
  expect(tab2).toBeDefined();

  fireEvent.click(tab2);
  expect(setActiveArtifactIdMock).toHaveBeenCalledWith('art2');
});

test('filters hidden artifacts and shows empty state if all are hidden', () => {
  useChat.mockReturnValue({
    workspaceArtifacts: [
      { id: '1', type: 'QuizCard', props: { question: 'What is React?' } },
    ],
    hiddenArtifactIds: ['1'],
  });
  render(<AgentWorkspace />);
  expect(screen.getByText(/暂无生成产物/)).toBeDefined();
});
