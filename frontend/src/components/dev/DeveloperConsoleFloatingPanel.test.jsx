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
        payload: { tool_name: 'read_learning_state', event: 'acting.end' }
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
  expect(screen.getByText('tool completed')).toBeInTheDocument();
  expect(screen.getByText('user_confirmation_required')).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '错误' }));

  expect(screen.queryByText('tool completed')).not.toBeInTheDocument();
  expect(screen.getByText('user_confirmation_required')).toBeInTheDocument();
});
