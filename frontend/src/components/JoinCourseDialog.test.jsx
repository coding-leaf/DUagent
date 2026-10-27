import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import JoinCourseDialog from './JoinCourseDialog';
import { courseService } from '../api/services/course';

vi.mock('../api/services/course', () => ({
  courseService: {
    joinCourse: vi.fn(),
  },
}));

describe('JoinCourseDialog', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<JoinCourseDialog open={false} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('displays backend detail message on 404', async () => {
    courseService.joinCourse.mockRejectedValueOnce({
      response: {
        status: 404,
        data: {
          detail: {
            code: 40400,
            message: '课程码不存在',
          },
        },
      },
    });

    render(<JoinCourseDialog open={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText(/输入课程码/);
    fireEvent.change(input, { target: { value: 'INVALID_CODE' } });

    const submitBtn = screen.getByRole('button', { name: /加入/ });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('课程码不存在')).toBeInTheDocument();
    });
  });

  it('displays backend top-level message if detail is absent', async () => {
    courseService.joinCourse.mockRejectedValueOnce({
      response: {
        status: 400,
        data: {
          message: '课程已加入或不可用',
        },
      },
    });

    render(<JoinCourseDialog open={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText(/输入课程码/);
    fireEvent.change(input, { target: { value: 'CODE_ALREADY_JOINED' } });

    const submitBtn = screen.getByRole('button', { name: /加入/ });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('课程已加入或不可用')).toBeInTheDocument();
    });
  });

  it('displays fallback message on network error without response', async () => {
    courseService.joinCourse.mockRejectedValueOnce(new Error('Network error'));

    render(<JoinCourseDialog open={true} onClose={vi.fn()} />);

    const input = screen.getByPlaceholderText(/输入课程码/);
    fireEvent.change(input, { target: { value: 'NETWORK_ERR' } });

    const submitBtn = screen.getByRole('button', { name: /加入/ });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('网络错误，请重试')).toBeInTheDocument();
    });
  });
});
