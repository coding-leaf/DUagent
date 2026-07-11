import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import PersonalizedResourceCard from './PersonalizedResourceCard';
import { PERSONALIZED_TYPE_META } from './resourceTypes';

describe('PersonalizedResourceCard', () => {
  it('defines the five competition resource types', () => {
    expect(Object.keys(PERSONALIZED_TYPE_META)).toEqual([
      'personal_lesson',
      'diagram',
      'practice',
      'reading',
      'validated_code_problem',
    ]);
  });

  it('shows source and non-blocking review advice', () => {
    render(
      <MemoryRouter>
        <PersonalizedResourceCard
          item={{
            id: 'link-1',
            source_type: 'learning_effects',
            resource_type: 'diagram',
            review_decision: 'approved_with_advice',
            review_warnings: ['可增加一个边界示例'],
            resource: {
              id: 'resource-1',
              title: '指针关系图',
              type: 'diagram',
              description: '数组与指针关系',
              knowledge_point: '指针',
            },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('知识图解')).toBeInTheDocument();
    expect(screen.getByText('学情建议')).toBeInTheDocument();
    expect(screen.getByText('审核通过（附建议）')).toBeInTheDocument();
    expect(screen.getByText('可增加一个边界示例')).toBeInTheDocument();
  });
});
