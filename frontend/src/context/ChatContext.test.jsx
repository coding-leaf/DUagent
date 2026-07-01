import { render, screen, act, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import { SWRConfig } from 'swr';
import { ChatProvider, useChat } from './ChatContext';
import { CourseProvider } from './CourseContext';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useLocation: () => ({ search: '', pathname: '' }),
  useNavigate: () => vi.fn()
}));

// Mock AuthContext
vi.mock('./AuthContext', () => ({
  useAuth: () => ({ user: { id: 'test-user-id' } })
}));

// Mock courseService
vi.mock('../api/services/course', () => ({
  courseService: {
    getMyCourses: vi.fn().mockResolvedValue({
      code: 200,
      data: { courses: [{ id: 'test-course-id', name: 'Test Course' }] }
    }),
    getReadyCatalogs: vi.fn().mockResolvedValue({ data: [] })
  }
}));

const streamChatMock = vi.hoisted(() => vi.fn());

// Mock chatService
vi.mock('../api/services/chat', () => ({
  chatService: {
    getSessions: vi.fn().mockResolvedValue({
      code: 200,
      data: { conversations: [{ id: 'conv-existing', title: 'Existing chat' }] }
    }),
    getHistory: vi.fn().mockResolvedValue({
      code: 200,
      data: { messages: [] }
    }),
    streamChat: (...args) => streamChatMock(...args)
  }
}));

beforeEach(() => {
  streamChatMock.mockReset();
  localStorage.clear();
});

const renderWithProviders = (ui) => render(
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    <CourseProvider>
      <ChatProvider>
        {ui}
      </ChatProvider>
    </CourseProvider>
  </SWRConfig>
);

const StreamConsumer = () => {
  const { activeSession, messages, workspaceArtifacts, sendMessage, resetConversation, isSending } = useChat();
  const assistant = messages.find(m => m.role === 'assistant');
  return (
    <div>
      <div data-testid="active-session">{activeSession || ''}</div>
      <div data-testid="message-count">{messages.length}</div>
      <div data-testid="assistant-content">{assistant?.content || ''}</div>
      <div data-testid="assistant-loading">{String(assistant?.loading ?? false)}</div>
      <div data-testid="assistant-error">{String(assistant?.isError ?? false)}</div>
      <div data-testid="tool-status">{assistant?.toolCalls?.[0]?.status || ''}</div>
      <div data-testid="artifact-count">{workspaceArtifacts.length}</div>
      <div data-testid="sending">{String(isSending)}</div>
      <button data-testid="send" onClick={() => sendMessage('hello')}>
        Send
      </button>
      <button data-testid="new-chat" onClick={() => resetConversation()}>
        New Chat
      </button>
    </div>
  );
};

test('keeps a user-created draft conversation active when history exists', async () => {
  renderWithProviders(<StreamConsumer />);

  await waitFor(() => {
    expect(screen.getByTestId('active-session').textContent).toBe('conv-existing');
  });

  await act(async () => {
    screen.getByTestId('new-chat').click();
  });

  expect(screen.getByTestId('active-session').textContent).toBe('');
  expect(screen.getByTestId('message-count').textContent).toBe('0');
});

test('ChatProvider reduces native EDU v2 stream events', async () => {
  streamChatMock.mockImplementation((_payload, onMessage) => {
    onMessage({
      type: 'workflow_started',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reply_id: 'reply-1' }
    });
    onMessage({
      type: 'tool_started',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { tool_call_id: 'tool-1', tool_name: 'TaskCreate' }
    });
    onMessage({
      type: 'text_delta',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { delta: 'hello' }
    });
    onMessage({
      type: 'tool_completed',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { tool_call_id: 'tool-1', state: 'success' }
    });
    onMessage({
      type: 'artifact_created',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { artifact: { id: 'artifact-1', type: 'Markdown', props: { content: '# Plan' } } }
    });
    onMessage({
      type: 'workflow_completed',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reply_id: 'reply-1' }
    });
    return vi.fn();
  });

  renderWithProviders(<StreamConsumer />);

  await waitFor(() => {
    expect(screen.getByTestId('active-session').textContent).toBe('conv-existing');
  });
  await act(async () => {
    screen.getByTestId('send').click();
  });

  await waitFor(() => {
    expect(screen.getByTestId('assistant-content').textContent).toBe('hello');
  });
  expect(screen.getByTestId('assistant-loading').textContent).toBe('false');
  expect(screen.getByTestId('tool-status').textContent).toBe('completed');
  expect(screen.getByTestId('artifact-count').textContent).toBe('1');
  expect(screen.getByTestId('sending').textContent).toBe('false');
});

test('ChatProvider handles workflow_failed as native EDU v2 error event', async () => {
  streamChatMock.mockImplementation((_payload, onMessage) => {
    onMessage({
      type: 'workflow_failed',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reason: 'model_not_configured', message: '模型未配置' }
    });
    return vi.fn();
  });

  renderWithProviders(<StreamConsumer />);

  await waitFor(() => {
    expect(screen.getByTestId('active-session').textContent).toBe('conv-existing');
  });
  await act(async () => {
    screen.getByTestId('send').click();
  });

  await waitFor(() => {
    expect(screen.getByTestId('assistant-loading').textContent).toBe('false');
  });
  expect(screen.getByTestId('assistant-error').textContent).toBe('true');
  expect(screen.getByTestId('assistant-content').textContent).toContain('模型未配置');
});
