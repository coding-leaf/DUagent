import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, test } from 'vitest';
import CodeProblemResourceCard from './CodeProblemResourceCard';

test('links a private code problem to its protected practice page', () => {
  render(
    <MemoryRouter>
      <CodeProblemResourceCard
        item={{
          id: 'link-1',
          source_type: 'ai_chat',
          code_problem: {
            id: 'problem-1',
            title: '统计元音字母',
            language: 'cpp',
            difficulty: 'easy',
            knowledge_point: '循环',
          },
        }}
      />
    </MemoryRouter>,
  );

  expect(screen.getByText('统计元音字母')).toBeInTheDocument();
  expect(screen.getByRole('link')).toHaveAttribute('href', '/code-problems/problem-1');
  expect(screen.getByText('C++')).toBeInTheDocument();
});
