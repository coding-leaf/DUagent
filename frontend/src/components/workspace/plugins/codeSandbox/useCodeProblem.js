import useSWR from 'swr';
import { getCodeProblem } from '../../../../api/services/codeProblems';

export const useCodeProblem = (problemId) => {
  const { data, error, isLoading } = useSWR(
    problemId ? ['code-problem', problemId] : null,
    () => getCodeProblem(problemId),
  );

  return {
    problem: data?.data || null,
    error,
    isLoading,
  };
};
