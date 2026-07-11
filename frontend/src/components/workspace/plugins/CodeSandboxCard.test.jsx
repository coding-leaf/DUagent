import { fireEvent, render, screen, waitFor, act } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import CodeSandboxCard from './codeSandbox/CodeSandboxCard';
import { executeSandboxCode } from '../../../api/services/sandbox';
import { getCodeProblem, submitCodeProblem } from '../../../api/services/codeProblems';
import { taskService } from '../../../api/services/task';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('../../../context/ChatContext', () => ({
  useChat: () => ({
    sendMessage: vi.fn(),
    isSending: false,
    resetConversation: vi.fn(),
  }),
}));

vi.mock('../../../api/services/sandbox', () => ({
  executeSandboxCode: vi.fn(),
}));

vi.mock('../../../api/services/codeProblems', () => ({
  getCodeProblem: vi.fn(),
  submitCodeProblem: vi.fn(),
}));

vi.mock('../../../api/services/task', () => ({
  taskService: { getTaskStatus: vi.fn() },
}));

vi.mock('sonner', () => ({
  toast: {
    promise: (promise, handlers) => promise.then(handlers.success, handlers.error),
    success: vi.fn(),
  },
}));

test('renders runtime errors as failed execution instead of completed run', async () => {
  executeSandboxCode.mockResolvedValue({
    data: {
      status: 'runtime_error',
      compile_status: 'OK',
      compile_output: '',
      execution: {
        stdout: '',
        stderr: 'Segmentation fault',
        exit_code: 139,
        status_description: 'Runtime Error (SIGSEGV)',
        run_time_ms: 10,
        memory_kb: 256,
      },
    },
  });

  render(
    <CodeSandboxCard
      question_text="修复崩溃"
      code="int main(){return *(int*)0;}"
      language="c"
      default_stdin=""
    />
  );

  fireEvent.click(screen.getByText('🚀 运行代码'));

  await waitFor(() => {
    expect(screen.getByText('运行失败')).toBeInTheDocument();
  });
  expect(screen.queryByText('运行完毕')).toBeNull();
});

test('uses fixed cases for persisted problems without exposing stdin input', async () => {
  getCodeProblem.mockResolvedValue({
    data: {
      title: '两数之和',
      statement: '读取两个整数并输出它们的和。',
      language: 'python',
      starter_code: 'a, b = map(int, input().split())',
      public_cases: [{ stdin: '1 2\n', expected_output: '3' }],
    },
  });
  submitCodeProblem.mockResolvedValue({ data: { task_id: 'task-1' } });
  taskService.getTaskStatus.mockResolvedValue({
    data: {
      status: 'completed',
      result: {
        status: 'wrong_answer',
        passed_cases: 1,
        total_cases: 2,
        failed_case: { visibility: 'hidden', message: '隐藏用例未通过' },
      },
    },
  });

  render(<CodeSandboxCard problem_id="problem-1" language="python" />);

  await screen.findByText('读取两个整数并输出它们的和。');
  expect(screen.queryByText('⌨️ 输入参数 (stdin)')).toBeNull();
  fireEvent.click(screen.getByText('🚀 提交评测'));

  await waitFor(() => {
    expect(screen.getByText('隐藏用例未通过')).toBeInTheDocument();
  });
  expect(submitCodeProblem).toHaveBeenCalledWith(expect.objectContaining({ problemId: 'problem-1' }));
  expect(screen.getByText('1 2')).toBeInTheDocument();
  expect(screen.queryByText('hidden input')).toBeNull();
});

test('supports language selection in free sandbox mode', async () => {
  render(
    <CodeSandboxCard
      question_text="自由编写代码"
      code=""
      language="python"
      default_stdin=""
    />
  );

  const select = screen.getByRole('combobox');
  expect(select).toBeInTheDocument();
  expect(select.value).toBe('python');

  act(() => {
    fireEvent.change(select, { target: { value: 'c' } });
  });
  await waitFor(() => {
    expect(select.value).toBe('c');
  });
  expect(screen.getByText('main.c')).toBeInTheDocument();
});
