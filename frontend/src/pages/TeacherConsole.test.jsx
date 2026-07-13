import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';
import TeacherConsole from './TeacherConsole';
import { useTeacherConsoleData } from '../hooks/useTeacherConsoleData';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'teacher', real_name: '王老师', role: 'teacher' } })
}));

vi.mock('../hooks/useTeacherConsoleData', () => ({
  useTeacherConsoleData: vi.fn()
}));

vi.mock('../components/CreateCourseDialog', () => ({
  default: () => null
}));

const consoleData = {
  classes: [{
    id: 'course-1',
    name: '2026 春季一班',
    catalog_title: '数据结构',
    course_code: 'DS2026',
    students: 2
  }],
  classesLoading: false,
  refreshClasses: vi.fn(),
  students: [
    { user_id: 'u1', username: '张同学', english_name: 'Zhang', student_id: '001', major: '计算机', grade: '大一', avatar_text: '张', avatar_color: 'bg-cyan-100' },
    { user_id: 'u2', username: '李同学', english_name: 'Li', student_id: '002', major: '计算机', grade: '大一', avatar_text: '李', avatar_color: 'bg-blue-100' }
  ],
  studentsLoading: false,
  studentsError: null,
  refreshStudents: vi.fn(),
  insights: {
    avg_quiz_score: 78.5,
    total_quiz_attempts: 12,
    weak_points_top: [],
    path_node_progress: { total_nodes: 8, completed: 2, in_progress: 3, recommended: 1, pending: 2 }
  },
  insightsLoading: false,
  insightsError: null,
  resources: [{ id: 'r1', title: '线性表', chapter: '第一章', type: 'lesson' }],
  resourcesLoading: false,
  resourcesError: null
};

beforeEach(() => {
  useTeacherConsoleData.mockReturnValue(consoleData);
});

test('uses the active class identity and dashboard-first section order', async () => {
  render(
    <MemoryRouter>
      <TeacherConsole />
    </MemoryRouter>
  );

  expect(await screen.findByTestId('teacher-console-title')).toHaveTextContent('2026 春季一班');
  expect(screen.queryByText('数据结构 (Data Structures)')).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '班级概览' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '学生学情与名单' })).toBeInTheDocument();

  const overview = screen.getByRole('heading', { name: '班级概览' });
  const students = screen.getByRole('heading', { name: '学生学情与名单' });
  const resources = screen.getByRole('heading', { name: '本班学习资源' });
  expect(overview.compareDocumentPosition(students) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(students.compareDocumentPosition(resources) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
