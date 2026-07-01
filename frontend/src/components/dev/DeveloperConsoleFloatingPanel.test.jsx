import { fireEvent, render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import DeveloperConsoleFloatingPanel from './DeveloperConsoleFloatingPanel';

vi.mock('../../context/ChatContext', () => ({
  useChat: () => ({
    runLogs: [
      {
        id: 'log-1',
        type: 'debug_log',
        level: 'info',
        message: 'tool completed',
        source: 'agent.middleware',
        runId: 'run-1',
        traceId: 'run-1',
        spanId: 'span-tool-1',
        payload: {
          event: 'tool.call.end',
          span_kind: 'tool',
          name: 'execute_tool read_learning_state',
          phase: 'end',
          span_id: 'span-tool-1',
          attributes: {
            tool_name: 'read_learning_state',
            tool_input_preview: '{"user_id":"u1"}',
            tool_output_preview: 'weak points: linked list',
            tool_state: 'success'
          }
        }
      },
      {
        id: 'log-2',
        type: 'workflow_failed',
        level: 'error',
        message: 'user_confirmation_required',
        source: 'workbench',
        runId: 'run-1',
        payload: { reason: 'user_confirmation_required' }
      }
    ],
    clearRunLogs: vi.fn()
  })
}));

vi.mock('../Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />
}));

test('renders floating developer console with logs', () => {
  render(<DeveloperConsoleFloatingPanel />);

  fireEvent.click(screen.getByRole('button', { name: /Dev/ }));

  expect(screen.getByText('Dev Console')).toBeInTheDocument();
  expect(screen.getByText('execute_tool read_learning_state')).toBeInTheDocument();
  expect(screen.getByText('tool/end')).toBeInTheDocument();
  expect(screen.getByText('user_confirmation_required')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '错误' }));

  expect(screen.queryByText('execute_tool read_learning_state')).not.toBeInTheDocument();
  expect(screen.getByText('user_confirmation_required')).toBeInTheDocument();
});

test('searches logs and expands payload details', () => {
  render(<DeveloperConsoleFloatingPanel />);

  fireEvent.click(screen.getByRole('button', { name: /Dev/ }));
  fireEvent.change(screen.getByPlaceholderText('搜索日志'), {
    target: { value: 'linked list' }
  });

  expect(screen.getByText('execute_tool read_learning_state')).toBeInTheDocument();
  expect(screen.queryByText('user_confirmation_required')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /execute_tool read_learning_state/ }));

  expect(screen.getByText(/tool_output_preview/)).toBeInTheDocument();
  expect(screen.getByText(/weak points: linked list/)).toBeInTheDocument();
});
