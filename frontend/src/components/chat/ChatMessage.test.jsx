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
});
