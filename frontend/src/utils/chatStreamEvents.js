export const updateTargetMessage = (messages, targetId, updater) => {
  return messages.map(m => m.id === targetId ? updater(m) : m);
};

const FAILED_TOOL_STATUSES = new Set(['rejected', 'degraded', 'unavailable']);

const isFailedToolResult = (payload = {}) => {
  return payload.state === 'error' || FAILED_TOOL_STATUSES.has(payload.status);
};

const toolOutputSummary = (payload = {}, isFailed = false) => {
  if (isFailed && payload.reason) return payload.reason;
  return payload.output_summary || payload.summary || payload.reason;
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

const appendTextPart = (parts = [], delta = '') => {
  if (!delta) return parts;
  const next = [...parts];
  const last = next.at(-1);
  if (last?.type === 'text') {
    next[next.length - 1] = { ...last, content: `${last.content || ''}${delta}` };
    return next;
  }
  return [...next, { type: 'text', content: delta }];
};

const upsertToolPart = (parts = [], update) => {
  const next = [...parts];
  const index = next.findIndex(part => part.type === 'tool' && part.toolCall?.id === update.id);
  if (index < 0) return [...next, { type: 'tool', toolCall: update }];
  next[index] = {
    ...next[index],
    toolCall: { ...next[index].toolCall, ...update }
  };
  return next;
};

const upsertPlanPart = (parts = [], tasks = []) => {
  const next = [...parts];
  const index = next.findIndex(part => part.type === 'plan');
  const planPart = { type: 'plan', tasks };
  if (index < 0) return [...next, planPart];
  next[index] = planPart;
  return next;
};

const appendSafetyReviewPart = (parts = [], review) => {
  if (!review || review.action === 'allow') return parts;
  return [...parts, { type: 'content_safety_review', review }];
};

const normalizeSafetyReview = (payload = {}) => ({
  passed: payload.passed !== false,
  riskLevel: payload.risk_level || payload.riskLevel || 'unknown',
  categories: Array.isArray(payload.categories) ? payload.categories : [],
  reason: payload.reason || '',
  action: payload.action || 'allow',
  scope: payload.scope || 'content_safety_only',
  knowledgeReviewed: payload.knowledge_reviewed === true
});

export const completeRunningParts = (parts = []) => {
  return parts.map(part => {
    if (part.type !== 'tool' || part.toolCall?.status !== 'running') return part;
    return { ...part, toolCall: { ...part.toolCall, status: 'completed' } };
  });
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
  toolCalls: [],
  parts: []
});

export const reduceAssistantMessageForEvent = (message, event) => {
  switch (event.type) {
    case 'workflow_started':
      return { ...message, runId: event.run_id || message.runId };
    case 'text_delta':
      return {
        ...message,
        content: message.content + (event.payload?.delta || ''),
        parts: appendTextPart(message.parts, event.payload?.delta || '')
      };
    case 'tool_started':
      {
        const toolCall = {
          id: event.payload?.tool_call_id || `tool-${crypto.randomUUID()}`,
          name: event.payload?.tool_name || '工具调用',
          status: 'running'
        };
        return {
          ...message,
          toolCalls: upsertToolCall(message.toolCalls, toolCall),
          parts: upsertToolPart(message.parts, toolCall)
        };
      }
    case 'tool_completed':
      {
        const isFailed = isFailedToolResult(event.payload);
        const toolCall = {
          id: event.payload?.tool_call_id || 'unknown',
          status: isFailed ? 'error' : 'completed',
          outputSummary: toolOutputSummary(event.payload, isFailed)
        };
        return {
          ...message,
          toolCalls: upsertToolCall(message.toolCalls, toolCall),
          parts: upsertToolPart(message.parts, toolCall)
        };
      }
    case 'tool_failed':
      {
        const toolCall = {
          id: event.payload?.tool_call_id || 'unknown',
          name: event.payload?.tool_name || '工具调用',
          status: 'error',
          outputSummary: event.payload?.reason || event.payload?.message
        };
        return {
          ...message,
          toolCalls: upsertToolCall(message.toolCalls, toolCall),
          parts: upsertToolPart(message.parts, toolCall)
        };
      }
    case 'plan_updated':
      return {
        ...message,
        parts: upsertPlanPart(message.parts, event.payload?.tasks || [])
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
    case 'content_safety_reviewed':
      {
        const review = normalizeSafetyReview(event.payload || {});
        return {
          ...message,
          safetyReview: review,
          safetyBlocked: review.action === 'block',
          safetyFlagged: review.action === 'flag',
          parts: appendSafetyReviewPart(message.parts, review)
        };
      }
    default:
      return message;
  }
};
