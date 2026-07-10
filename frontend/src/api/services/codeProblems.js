import apiClient from '../client';

export const getCodeProblem = (problemId) => apiClient.get(`/code-problems/${problemId}`);

export const submitCodeProblem = ({ problemId, code }) => apiClient.post(
  `/code-problems/${problemId}/submissions`,
  { code },
);
