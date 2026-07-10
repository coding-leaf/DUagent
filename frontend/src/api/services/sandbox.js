import apiClient from '../client';

export const executeSandboxCode = ({ code, language, stdin = '' }) => {
  return apiClient.post('/sandbox/execute', {
    code,
    language,
    stdin,
  });
};
