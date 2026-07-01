import { useCallback, useState } from 'react';

const MAX_RUN_LOGS = 300;

const normalizeRunLog = (event) => {
  const payload = event.payload || {};
  return {
    id: `${event.run_id || 'local'}-${event.seq || Date.now()}-${crypto.randomUUID()}`,
    type: event.type || 'unknown',
    level: payload.level || (event.type === 'workflow_failed' ? 'error' : 'info'),
    message: payload.message || payload.event || event.type || 'unknown',
    source: payload.source || event.agent || 'sse',
    runId: event.run_id || null,
    conversationId: event.conversation_id || null,
    timestamp: event.timestamp || new Date().toISOString(),
    payload
  };
};

export const useRunLogs = () => {
  const [runLogs, setRunLogs] = useState([]);

  const appendRunLog = useCallback((event) => {
    setRunLogs(prev => [...prev.slice(-(MAX_RUN_LOGS - 1)), normalizeRunLog(event)]);
  }, []);

  const clearRunLogs = useCallback(() => setRunLogs([]), []);

  return {
    runLogs,
    appendRunLog,
    clearRunLogs
  };
};
