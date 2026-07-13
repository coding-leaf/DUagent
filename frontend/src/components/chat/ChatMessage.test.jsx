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

    expect(screen.getByText('抱歉，我无法回答你的问题。')).toBeDefined();
    expect(screen.getByText('检测到内容安全风险，回答已自动终止。')).toBeDefined();
    expect(screen.queryByText('不应展示的原文')).toBeNull();
    expect(screen.queryByText('明确违法指导')).toBeNull();
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

  it('filters out redundant planning tool call cards when a plan part is present', () => {
    render(
      <ChatMessage
        message={{
          id: 'ai-plan-test',
          role: 'assistant',
          content: '',
          loading: false,
          parts: [
            {
              type: 'tool',
              toolCall: {
                id: 'tool-create',
                name: 'TaskCreate',
                status: 'completed'
              }
            },
            {
              type: 'tool',
              toolCall: {
                id: 'tool-oj',
                name: 'run_code_in_oj',
                status: 'completed'
              }
            },
            {
              type: 'plan',
              tasks: [
                { id: '1', title: '编写二叉树程序', status: 'completed' }
              ]
            }
          ]
        }}
        onSendMessage={vi.fn()}
        onRegenerate={vi.fn()}
      />
    );

    // 具体的 AI 计划任务列表应该正常呈现
    expect(screen.getByText('AI 计划')).toBeDefined();
    expect(screen.getByText('编写二叉树程序')).toBeDefined();

    // 普通业务工具卡片（如在线沙盒编译运行）应该正常呈现
    expect(screen.getByText('在线沙盒编译运行')).toBeDefined();

    // 内部的 TaskCreate 管理卡片因与 plan panel 并存，应被自动隐藏，不呈现在屏幕上
    expect(screen.queryByText('创建计划任务')).toBeNull();
  });
});
