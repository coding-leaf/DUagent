import { describe, expect, it, vi } from 'vitest';
import {
  createEmptyAiMessage,
  reduceAssistantMessageForEvent
} from '../chatStreamEvents';

describe('chatStreamEvents', () => {
  it('keeps text and tool calls in stream arrival order', () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('generated-id');
    let message = createEmptyAiMessage();

    message = reduceAssistantMessageForEvent(message, {
      type: 'text_delta',
      payload: { delta: '好的，我先查看你的学习状态。' }
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_started',
      payload: { tool_call_id: 'tool-1', tool_name: 'read_learning_state' }
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_completed',
      payload: { tool_call_id: 'tool-1', state: 'success', summary: '薄弱点已读取' }
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'text_delta',
      payload: { delta: '接下来我会生成补弱计划。' }
    });

    expect(message.parts).toEqual([
      { type: 'text', content: '好的，我先查看你的学习状态。' },
      {
        type: 'tool',
        toolCall: {
          id: 'tool-1',
          name: 'read_learning_state',
          status: 'completed',
          outputSummary: '薄弱点已读取'
        }
      },
      { type: 'text', content: '接下来我会生成补弱计划。' }
    ]);
    expect(message.content).toBe('好的，我先查看你的学习状态。接下来我会生成补弱计划。');
  });
});
