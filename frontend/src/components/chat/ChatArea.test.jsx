import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import ChatArea from './ChatArea';

const chatState = vi.hoisted(() => ({
  sendMessage: vi.fn(),
  runMockToolDemo: vi.fn()
}));

vi.mock('../../context/ChatContext', () => ({
  useChat: () => ({
    sessions: [],
    activeSession: null,
    messages: [],
    isSending: false,
    sendMessage: chatState.sendMessage,
    editMessage: vi.fn(),
    cancelStream: vi.fn(),
    regenerate: vi.fn(),
    runMockToolDemo: chatState.runMockToolDemo
  })
}));

vi.mock('../../context/CourseContext', () => ({
  useCourse: () => ({ activeCourseId: 'course-1' })
}));

vi.mock('./ChatEmptyState', () => ({
  default: () => <div data-testid="empty-state" />
}));

vi.mock('./ChatMessage', () => ({
  default: () => <div data-testid="chat-message" />
}));

vi.mock('../Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />
}));

beforeEach(() => {
  chatState.sendMessage.mockReset();
  chatState.runMockToolDemo.mockReset();
});

test('submits quick action prompts through sendMessage instead of mock demos', () => {
  render(<ChatArea activeCourseName="Test Course" onOpenLeftDrawer={vi.fn()} />);

  fireEvent.click(screen.getByRole('button', { name: /补弱计划/ }));

  expect(chatState.sendMessage).toHaveBeenCalledWith('帮我根据当前薄弱点生成补弱学习计划。');
  expect(chatState.runMockToolDemo).not.toHaveBeenCalled();
});

test('toggles plan mode and applies it to the next sent message', () => {
  render(<ChatArea activeCourseName="Test Course" onOpenLeftDrawer={vi.fn()} />);

  fireEvent.click(screen.getByRole('button', { name: /计划模式/ }));
  fireEvent.change(screen.getByPlaceholderText('在这里输入你的问题...'), {
    target: { value: '帮我分析薄弱点' }
  });
  fireEvent.click(screen.getByTestId('send-message-button'));

  expect(chatState.sendMessage).toHaveBeenCalledWith('帮我分析薄弱点', { planMode: true });
  expect(chatState.runMockToolDemo).not.toHaveBeenCalled();
});
