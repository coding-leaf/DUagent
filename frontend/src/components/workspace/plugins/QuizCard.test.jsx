import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import QuizCard from './QuizCard';

const navigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
}));

beforeEach(() => navigate.mockReset());

test('launches a persisted private quiz through the formal quiz page', () => {
  render(<QuizCard course_id="course-1" question_ids={['q1', 'q2']} />);

  expect(screen.getByText('仅自己可见')).toBeInTheDocument();
  fireEvent.click(screen.getByText('开始练习'));

  expect(navigate).toHaveBeenCalledWith(
    '/quiz?course_id=course-1&source=personalized&question_ids=q1%2Cq2'
  );
});
