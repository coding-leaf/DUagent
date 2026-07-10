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

  it('adds plan updates as ordered message parts', () => {
    let message = createEmptyAiMessage();

    message = reduceAssistantMessageForEvent(message, {
      type: 'text_delta',
      payload: { delta: '我会先拆解任务。' }
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'plan_updated',
      payload: {
        tasks: [
          { id: '1', title: '查询学习状态', description: '读取薄弱点', status: 'in_progress' },
          { id: '2', title: '生成补弱计划', description: '输出计划', status: 'pending' }
        ]
      }
    });

    expect(message.parts).toEqual([
      { type: 'text', content: '我会先拆解任务。' },
      {
        type: 'plan',
        tasks: [
          { id: '1', title: '查询学习状态', description: '读取薄弱点', status: 'in_progress' },
          { id: '2', title: '生成补弱计划', description: '输出计划', status: 'pending' }
        ]
      }
    ]);
  });

  it('marks rejected tool results as errors even when AgentScope completed the call', () => {
    let message = createEmptyAiMessage();
    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_started',
      payload: { tool_call_id: 'tool-1', tool_name: 'create_validated_personal_code_problem' }
    });

    message = reduceAssistantMessageForEvent(message, {
      type: 'tool_completed',
      payload: {
        tool_call_id: 'tool-1',
        state: 'success',
        status: 'rejected',
        reason: 'backend_validation_error'
      }
    });

    expect(message.toolCalls[0]).toMatchObject({
      status: 'error',
      outputSummary: 'backend_validation_error'
    });
  });

  it('adds content safety review as an ordered message part and blocks critical content', () => {
    let message = createEmptyAiMessage();

    message = reduceAssistantMessageForEvent(message, {
      type: 'text_delta',
      payload: { delta: '原始回答' }
    });
    message = reduceAssistantMessageForEvent(message, {
      type: 'content_safety_reviewed',
      payload: {
        passed: false,
        risk_level: 'critical',
        categories: ['illegal_instruction'],
        reason: '明确违法指导',
        action: 'block',
        scope: 'content_safety_only',
        knowledge_reviewed: false
      }
    });

    expect(message.safetyReview).toEqual({
      passed: false,
      riskLevel: 'critical',
      categories: ['illegal_instruction'],
      reason: '明确违法指导',
      action: 'block',
      scope: 'content_safety_only',
      knowledgeReviewed: false
    });
    expect(message.safetyBlocked).toBe(true);
    expect(message.parts).toEqual([
      { type: 'text', content: '原始回答' },
      {
        type: 'content_safety_review',
        review: message.safetyReview
      }
    ]);
  });
});
