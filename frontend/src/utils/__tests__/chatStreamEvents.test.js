import { describe, expect, it } from 'vitest';
import {
  createEmptyAiMessage,
  reduceAssistantMessageForEvent,
} from '../chatStreamEvents';

describe('chatStreamEvents', () => {
  it('keeps text and tool events in stream order', () => {
    let message = createEmptyAiMessage();

    message = reduceAssistantMessageForEvent(message, {
      type: 'text_delta',
      payload: { delta: '好的，我会先查询内容。' },
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_started',
      payload: { tool_call_id: 'tool-1', tool_name: 'read_learning_state' },
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'text_delta',
      payload: { delta: '接下来查询课程资料。' },
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_started',
      payload: { tool_call_id: 'tool-2', tool_name: 'search_knowledge' },
    });

    expect(message.parts).toEqual([
      { type: 'text', content: '好的，我会先查询内容。' },
      {
        type: 'tool',
        toolCall: {
          id: 'tool-1',
          name: 'read_learning_state',
          status: 'running',
        },
      },
      { type: 'text', content: '接下来查询课程资料。' },
      {
        type: 'tool',
        toolCall: {
          id: 'tool-2',
          name: 'search_knowledge',
          status: 'running',
        },
      },
    ]);
  });
});
