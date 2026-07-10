import { describe, expect, test } from 'vitest';
import {
  buildAskAIPrompt,
  getResultBadge,
  getRunToastMessage,
  isExecutionFailure
} from './codeSandboxViewModel';

describe('codeSandboxViewModel', () => {
  test('marks runtime errors as execution failures', () => {
    const result = {
      status: 'runtime_error',
      compile_status: 'OK',
      execution: {
        stderr: 'Segmentation fault',
        exit_code: 139,
        status_description: 'Runtime Error (SIGSEGV)',
      },
    };

    expect(isExecutionFailure(result)).toBe(true);
    expect(getResultBadge(result).label).toBe('运行失败');
    expect(getRunToastMessage(result)).toBe('程序运行失败，请查看终端输出');
  });

  test('keeps successful execution as completed run', () => {
    const result = {
      status: 'success',
      compile_status: 'OK',
      execution: {
        stdout: 'hello',
        stderr: '',
        exit_code: 0,
      },
    };

    expect(isExecutionFailure(result)).toBe(false);
    expect(getResultBadge(result).label).toBe('运行完毕');
    expect(getRunToastMessage(result)).toBe('代码运行完成');
  });

  test('labels fixed-case verdicts without treating wrong answers as runtime failures', () => {
    expect(getResultBadge({ status: 'accepted' }).label).toBe('全部通过');
    expect(getResultBadge({ status: 'wrong_answer' }).label).toBe('用例未通过');
  });

  test('builds ask-ai prompt with current code and execution details', () => {
    const prompt = buildAskAIPrompt({
      code: 'print(1 / 0)',
      language: 'python',
      stdin: '',
      result: {
        status: 'runtime_error',
        compile_status: 'OK',
        execution: {
          stdout: '',
          stderr: 'ZeroDivisionError',
          exit_code: 1,
        },
      },
    });

    expect(prompt).toContain('```python');
    expect(prompt).toContain('print(1 / 0)');
    expect(prompt).toContain('ZeroDivisionError');
    expect(prompt).toContain('Exit Code 1');
  });
});
