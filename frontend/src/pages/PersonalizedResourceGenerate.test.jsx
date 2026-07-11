import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { personalizedResourcesService } from '../api/services/personalizedResources';
import PersonalizedResourceGenerate from './PersonalizedResourceGenerate';

vi.mock('../api/services/personalizedResources', () => ({
  personalizedResourcesService: { generate: vi.fn() },
}));
vi.mock('../context/CourseContext', () => ({
  useCourse: () => ({ activeCourseId: 'course-1' }),
}));
vi.mock('../components/Navbar', () => ({ default: () => <div>navbar</div> }));

describe('PersonalizedResourceGenerate', () => {
  beforeEach(() => vi.clearAllMocks());

  it('submits a natural-language goal with selected resource preferences', async () => {
    personalizedResourcesService.generate.mockResolvedValue({
      code: 202,
      data: { task_id: 'task-1', status: 'started' },
    });
    render(<MemoryRouter><PersonalizedResourceGenerate /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText('学习目标'), {
      target: { value: '针对指针薄弱点生成讲义和思维导图' },
    });
    fireEvent.click(screen.getByRole('checkbox', { name: '专业课程讲解' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '知识点思维导图' }));
    fireEvent.click(screen.getByRole('button', { name: '启动多智能体生成' }));

    await waitFor(() => expect(personalizedResourcesService.generate).toHaveBeenCalledWith({
      course_id: 'course-1',
      goal: '针对指针薄弱点生成讲义和思维导图',
      source_type: 'manual',
      resource_preferences: ['personal_lesson', 'diagram'],
    }));
  });
});
