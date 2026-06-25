import { render, screen, act } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { ChatProvider, useChat } from './ChatContext';
import { CourseProvider } from './CourseContext';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useLocation: () => ({ search: '', pathname: '' }),
  useNavigate: () => vi.fn()
}));

// Mock AuthContext
vi.mock('./AuthContext', () => ({
  useAuth: () => ({ user: { id: 'test-user-id' } })
}));

// Mock courseService
vi.mock('../api/services/course', () => ({
  courseService: {
    getMyCourses: vi.fn().mockResolvedValue({
      code: 200,
      data: { courses: [{ id: 'test-course-id', name: 'Test Course' }] }
    }),
    getReadyCatalogs: vi.fn().mockResolvedValue({ data: [] })
  }
}));

// Mock chatService
vi.mock('../api/services/chat', () => ({
  chatService: {
    getSessions: vi.fn().mockResolvedValue({
      code: 200,
      data: { conversations: [] }
    }),
    getHistory: vi.fn().mockResolvedValue({
      code: 200,
      data: { messages: [] }
    })
  }
}));

const TestConsumer = () => {
  const { workspaceArtifacts, sendMockArtifact } = useChat();
  return (
    <div>
      <div data-testid="count">{workspaceArtifacts.length}</div>
      <button data-testid="trigger" onClick={() => sendMockArtifact({ type: 'QuizCard', props: { question: 'Test?' } })}>
        Trigger
      </button>
    </div>
  );
};

test('workspaceArtifacts state manages active workspace plugin payloads', async () => {
  render(
    <CourseProvider>
      <ChatProvider>
        <TestConsumer />
      </ChatProvider>
    </CourseProvider>
  );

  expect(screen.getByTestId('count').textContent).toBe('0');
  
  await act(async () => {
    screen.getByTestId('trigger').click();
  });

  expect(screen.getByTestId('count').textContent).toBe('1');
});
