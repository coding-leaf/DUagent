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

test('submits plan mode as an agent intent prompt instead of a fixed workflow', () => {
  render(<ChatArea activeCourseName="Test Course" onOpenLeftDrawer={vi.fn()} />);

  fireEvent.click(screen.getByRole('button', { name: /计划模式/ }));

  expect(chatState.sendMessage).toHaveBeenCalledWith(
    '请先制定一个简短执行计划，再根据计划调用必要工具完成我的学习请求。'
  );
  expect(chatState.runMockToolDemo).not.toHaveBeenCalled();
});
