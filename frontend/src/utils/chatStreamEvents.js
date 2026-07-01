export const updateTargetMessage = (messages, targetId, updater) => {
  return messages.map(m => m.id === targetId ? updater(m) : m);
};

export const completeRunningToolCalls = (toolCalls = []) => {
  return toolCalls.map(tc => tc.status === 'running' ? { ...tc, status: 'completed' } : tc);
};

export const upsertToolCall = (toolCalls = [], update) => {
  const id = update.id;
  const existing = toolCalls.find(tc => tc.id === id);
  if (!existing) return [...toolCalls, update];
  return toolCalls.map(tc => tc.id === id ? { ...tc, ...update } : tc);
};

export const normalizeArtifact = (event) => {
  const artifact = event.payload?.artifact;
  if (!artifact || !artifact.type) return null;
  return {
    id: artifact.id || `artifact-${crypto.randomUUID()}`,
    type: artifact.type,
    props: artifact.props || {},
    timestamp: event.timestamp || new Date().toISOString()
  };
};

export const completionMessageId = (event) => {
  return event.message_id || event.payload?.message_id || `ai-${crypto.randomUUID()}`;
};

export const createEmptyAiMessage = (id = 'ai-placeholder') => ({
  id,
  role: 'assistant',
  content: '',
  loading: true,
  diagrams: [],
  knowledge_points: [],
  suggestions: [],
  toolCalls: []
});

export const reduceAssistantMessageForEvent = (message, event) => {
  switch (event.type) {
    case 'workflow_started':
      return { ...message, runId: event.run_id || message.runId };
    case 'text_delta':
      return { ...message, content: message.content + (event.payload?.delta || '') };
    case 'tool_started':
      return {
        ...message,
        toolCalls: upsertToolCall(message.toolCalls, {
          id: event.payload?.tool_call_id || `tool-${crypto.randomUUID()}`,
          name: event.payload?.tool_name || '工具调用',
          status: 'running'
        })
      };
    case 'tool_completed':
      return {
        ...message,
        toolCalls: upsertToolCall(message.toolCalls, {
          id: event.payload?.tool_call_id || 'unknown',
          status: event.payload?.state === 'error' ? 'error' : 'completed',
          outputSummary: event.payload?.summary
        })
      };
    case 'tool_failed':
      return {
        ...message,
        toolCalls: upsertToolCall(message.toolCalls, {
          id: event.payload?.tool_call_id || 'unknown',
          name: event.payload?.tool_name || '工具调用',
          status: 'error',
          outputSummary: event.payload?.reason || event.payload?.message
        })
      };
    case 'source_refs':
      return {
        ...message,
        sourceRefs: event.payload?.sources || []
      };
    case 'critic_completed':
      return {
        ...message,
        reviewFlagged: event.payload?.passed === false,
        reviewReason: event.payload?.reason || message.reviewReason
      };
    default:
      return message;
  }
};
