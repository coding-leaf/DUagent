import { render, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import Dashboard from './Dashboard';
import { learningService } from '../api/services/learning';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ state: { search: '变量与数据类型' } }),
}));

vi.mock('../context/CourseContext', () => ({
  useCourse: () => ({
    activeCourseId: 'class-course',
    loading: false,
    changeCourse: vi.fn(),
    refreshCourses: vi.fn(),
  }),
}));

vi.mock('../api/services/learning', () => ({
  learningService: { getResources: vi.fn() },
}));

vi.mock('../components/Navbar', () => ({
  default: () => <div>Navbar</div>,
}));

beforeEach(() => {
  learningService.getResources.mockReset();
  learningService.getResources.mockResolvedValue({
    code: 200,
    data: { resources: [] },
  });
});

test('queries the backend with the learning-path node keyword before pagination', async () => {
  render(<Dashboard />);

  await waitFor(() => {
    expect(learningService.getResources).toHaveBeenCalledWith({
      course_id: 'class-course',
      keyword: '变量与数据类型',
      page: 1,
      page_size: 50,
    });
  });
});
