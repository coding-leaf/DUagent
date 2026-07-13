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
const getHistoryMock = vi.hoisted(() => vi.fn());

// Mock chatService
vi.mock('../api/services/chat', () => ({
  chatService: {
    getSessions: vi.fn().mockResolvedValue({
      code: 200,
      data: {
        conversations: [
          { id: 'conv-existing', title: 'Existing chat' },
          { id: 'conv-saved', title: 'Saved chat' }
        ]
      }
    }),
    getHistory: (...args) => getHistoryMock(...args),
    streamChat: (...args) => streamChatMock(...args)
  }
}));

beforeEach(() => {
  streamChatMock.mockReset();
  getHistoryMock.mockReset();
  getHistoryMock.mockResolvedValue({
    code: 200,
    data: { messages: [] }
  });
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
  const {
    activeSession, messages, workspaceArtifacts, activeArtifactId,
    runLogs, clearRunLogs, sendMessage, resetConversation, isSending,
    hiddenArtifactIds, hideArtifact, restoreArtifact
  } = useChat();
  const assistant = messages.find(m => m.role === 'assistant');
  const user = messages.find(m => m.role === 'user');
  return (
    <div>
      <div data-testid="active-session">{activeSession || ''}</div>
      <div data-testid="message-count">{messages.length}</div>
      <div data-testid="user-content">{user?.content || ''}</div>
      <div data-testid="assistant-content">{assistant?.content || ''}</div>
      <div data-testid="assistant-parts">
        {(assistant?.parts || []).map(part => part.content || '').join('')}
      </div>
      <div data-testid="assistant-loading">{String(assistant?.loading ?? false)}</div>
      <div data-testid="assistant-error">{String(assistant?.isError ?? false)}</div>
      <div data-testid="tool-status">{assistant?.toolCalls?.[0]?.status || ''}</div>
      <div data-testid="artifact-count">{workspaceArtifacts.length}</div>
      <div data-testid="active-artifact-id">{activeArtifactId || ''}</div>
      <div data-testid="log-count">{runLogs?.length || 0}</div>
      <div data-testid="last-log-message">{runLogs?.at(-1)?.message || ''}</div>
      <div data-testid="sending">{String(isSending)}</div>
      <div data-testid="hidden-count">{hiddenArtifactIds?.length || 0}</div>
      <button data-testid="send" onClick={() => sendMessage('hello')}>
        Send
      </button>
      <button data-testid="send-plan" onClick={() => sendMessage('hello', { planMode: true })}>
        Send Plan
      </button>
      <button data-testid="new-chat" onClick={() => resetConversation()}>
        New Chat
      </button>
      <button data-testid="clear-logs" onClick={() => clearRunLogs()}>
        Clear Logs
      </button>
      <button data-testid="hide-artifact" onClick={() => hideArtifact('artifact-plan')}>
        Hide
      </button>
      <button data-testid="restore-artifact" onClick={() => restoreArtifact('artifact-plan')}>
        Restore
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

test('restores the last active conversation for the current course', async () => {
  localStorage.setItem('active_session_id_test-course-id', 'conv-saved');

  renderWithProviders(<StreamConsumer />);

  await waitFor(() => {
    expect(screen.getByTestId('active-session').textContent).toBe('conv-saved');
  });
});

test('ChatProvider keeps original user text while sending plan hint to agent', async () => {
  streamChatMock.mockImplementation((_payload, onMessage) => {
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
    screen.getByTestId('send-plan').click();
  });

  expect(screen.getByTestId('user-content').textContent).toBe('hello');
  expect(streamChatMock.mock.calls[0][0].message).toContain('请先制定一个简短执行计划');
  expect(streamChatMock.mock.calls[0][0].message).toContain('用户请求：\nhello');
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
  expect(screen.getByTestId('active-artifact-id').textContent).toBe('artifact-1');
  expect(screen.getByTestId('sending').textContent).toBe('false');
});

test('ChatProvider restores workspace artifacts from conversation history', async () => {
  getHistoryMock.mockResolvedValue({
    code: 200,
    data: {
      messages: [
        {
          role: 'assistant',
          content: '已生成补弱计划。',
          meta: {
            artifacts: [
              {
                id: 'artifact-plan',
                type: 'Markdown',
                props: { title: '补弱计划', content: '# 补弱计划' }
              }
            ]
          }
        }
      ]
    }
  });

  renderWithProviders(<StreamConsumer />);

  await waitFor(() => {
    expect(screen.getByTestId('active-session').textContent).toBe('conv-existing');
  });
  await waitFor(() => {
    expect(screen.getByTestId('artifact-count').textContent).toBe('1');
  });
  expect(screen.getByTestId('active-artifact-id').textContent).toBe('artifact-plan');
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
  expect(screen.getByTestId('assistant-parts').textContent).toContain('模型未配置');
});

test('ChatProvider records native stream and debug events for developer console', async () => {
  streamChatMock.mockImplementation((_payload, onMessage) => {
    onMessage({
      type: 'workflow_started',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: { reply_id: 'reply-1' }
    });
    onMessage({
      type: 'debug_log',
      run_id: 'run-1',
      conversation_id: 'conv-1',
      message_id: 'msg-1',
      payload: {
        level: 'info',
        source: 'agent.middleware',
        message: 'tool started',
        tool_name: 'read_learning_state'
      }
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
    expect(screen.getByTestId('log-count').textContent).toBe('3');
  });
  expect(screen.getByTestId('last-log-message').textContent).toBe('workflow_completed');

  await act(async () => {
    screen.getByTestId('clear-logs').click();
  });
  expect(screen.getByTestId('log-count').textContent).toBe('0');
});

test('handles hiding and restoring artifacts', async () => {
  getHistoryMock.mockResolvedValue({
    code: 200,
    data: {
      messages: [
        {
          role: 'assistant',
          content: '已生成补弱计划。',
          meta: {
            artifacts: [
              {
                id: 'artifact-plan',
                type: 'Markdown',
                props: { title: '补弱计划', content: '# 补弱计划' }
              }
            ]
          }
        }
      ]
    }
  });

  renderWithProviders(<StreamConsumer />);

  await waitFor(() => {
    expect(screen.getByTestId('artifact-count').textContent).toBe('1');
  });
  expect(screen.getByTestId('active-artifact-id').textContent).toBe('artifact-plan');
  expect(screen.getByTestId('hidden-count').textContent).toBe('0');

  await act(async () => {
    screen.getByTestId('hide-artifact').click();
  });
  expect(screen.getByTestId('hidden-count').textContent).toBe('1');
  expect(screen.getByTestId('active-artifact-id').textContent).toBe('');

  await act(async () => {
    screen.getByTestId('restore-artifact').click();
  });
  expect(screen.getByTestId('hidden-count').textContent).toBe('0');
  expect(screen.getByTestId('active-artifact-id').textContent).toBe('artifact-plan');
});
