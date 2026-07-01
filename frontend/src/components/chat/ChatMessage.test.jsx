import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ChatMessage from './ChatMessage';

describe('ChatMessage', () => {
  it('renders plan parts as an AI task list', () => {
    render(
      <ChatMessage
        message={{
          id: 'ai-1',
          role: 'assistant',
          content: '',
          loading: true,
          parts: [
            {
              type: 'plan',
              tasks: [
                { id: '1', title: '查询学习状态', description: '读取薄弱点', status: 'in_progress' },
                { id: '2', title: '生成补弱计划', description: '输出计划', status: 'pending' }
              ]
            }
          ]
        }}
        onSendMessage={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    expect(screen.getByText('AI 计划')).toBeDefined();
    expect(screen.getByText('查询学习状态')).toBeDefined();
    expect(screen.getByText('进行中')).toBeDefined();
    expect(screen.getByText('生成补弱计划')).toBeDefined();
    expect(screen.getByText('待执行')).toBeDefined();
  });

  it('replaces blocked assistant content with safety notice', () => {
    render(
      <ChatMessage
        message={{
          id: 'ai-1',
          role: 'assistant',
          content: '不应展示的原文',
          loading: false,
          safetyBlocked: true,
          safetyReview: {
            action: 'block',
            riskLevel: 'critical',
            reason: '明确违法指导'
          },
          parts: [
            { type: 'text', content: '不应展示的原文' },
            {
              type: 'content_safety_review',
              review: {
                action: 'block',
                riskLevel: 'critical',
                reason: '明确违法指导'
              }
            }
          ]
        }}
        onSendMessage={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    expect(screen.getByText('该回复未通过内容安全审核，已隐藏。')).toBeDefined();
    expect(screen.queryByText('不应展示的原文')).toBeNull();
    expect(screen.getByText('明确违法指导')).toBeDefined();
  });

  it('renders a tool call without duplicating the raw tool name', () => {
    render(
      <ChatMessage
        message={{
          id: 'ai-1',
          role: 'assistant',
          content: '',
          loading: true,
          parts: [
            {
              type: 'tool',
              toolCall: {
                id: 'tool-1',
                name: 'TaskCreate',
                status: 'completed'
              }
            }
          ]
        }}
        onSendMessage={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    expect(screen.getByText('创建计划任务')).toBeDefined();
    expect(screen.queryByText('TaskCreate')).toBeNull();
  });
});
