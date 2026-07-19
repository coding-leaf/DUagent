import { useEffect, useState } from 'react';
import useSWR from 'swr';
import { toast } from 'sonner';
import { executeSandboxCode } from '../../../../api/services/sandbox';
import { submitCodeProblem } from '../../../../api/services/codeProblems';
import { taskService } from '../../../../api/services/task';
import { getRunToastMessage } from './codeSandboxViewModel';

export const useCodeSandboxExecution = ({ initialCode, defaultStdin, language, problemId }) => {
  const [code, setCode] = useState(initialCode || '');
  const [stdin, setStdin] = useState(defaultStdin || '');
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [taskId, setTaskId] = useState(null);

  useEffect(() => {
    if (initialCode) queueMicrotask(() => setCode(initialCode));
  }, [initialCode]);

  const { data: taskResponse } = useSWR(
    taskId ? ['code-problem-task', taskId] : null,
    () => taskService.getTaskStatus(taskId),
    {
      refreshInterval: (response) => (response?.data?.status === 'processing' ? 1000 : 0),
    },
  );

  useEffect(() => {
    const task = taskResponse?.data;
    if (!task || task.status === 'processing') return;
    queueMicrotask(() => {
      setIsRunning(false);
      setResult(task.result || {
        status: 'degraded',
        message: task.error_message || '判题任务失败',
      });
    });
  }, [taskResponse]);

  const runCode = () => {
    if (isRunning) return;
    setIsRunning(true);
    setResult(null);

    if (problemId) {
      submitCodeProblem({ problemId, code })
        .then((response) => {
          setTaskId(response.data.task_id);
          toast.success('已提交固定用例评测');
        })
        .catch((err) => {
          setIsRunning(false);
          setResult({ status: 'degraded', message: err.message || '提交失败' });
        });
      return;
    }

    const promise = executeSandboxCode({
      code,
      language,
      stdin,
    });

    toast.promise(promise, {
      loading: '正在编译并运行代码...',
      success: (res) => {
        setIsRunning(false);
        const data = res.data;
        setResult(data);
        return getRunToastMessage(data);
      },
      error: (err) => {
        setIsRunning(false);
        setResult({
          status: 'degraded',
          compile_status: 'UNKNOWN',
          execution: null,
          message: err.message || '网络连接失败',
        });
        return '运行失败，已启用容错模式';
      },
    });
  };

  return {
    code,
    setCode,
    stdin,
    setStdin,
    isRunning,
    result,
    runCode,
    isFixedCaseProblem: Boolean(problemId),
  };
};
