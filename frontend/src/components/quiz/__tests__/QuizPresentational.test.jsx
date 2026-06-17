import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import QuizHeader from '../QuizHeader';
import QuizSidebar from '../QuizSidebar';
import QuizFooter from '../QuizFooter';

vi.mock('../../Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`}>{name}</span>
}));

describe('QuizHeader', () => {
  it('renders course name and progress', () => {
    const onExit = vi.fn();
    render(
      <QuizHeader 
        currentQuestionIndex={2} 
        totalQuestions={10} 
        courseName="Test Course" 
        onExit={onExit} 
      />
    );
    expect(screen.getByText('Test Course')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument(); // currentQuestionIndex + 1
    expect(screen.getByText('/ 10 题')).toBeInTheDocument();
    
    // Simulate exit click
    fireEvent.click(screen.getByTitle(/返回上一页/i));
    expect(onExit).toHaveBeenCalled();
  });
});

describe('QuizSidebar', () => {
  it('renders metadata', () => {
    render(
      <QuizSidebar 
        difficulty="hard"
        knowledgePoint="Test Knowledge"
        questionTypeLabel="Single Choice"
      />
    );
    expect(screen.getByText('Test Knowledge')).toBeInTheDocument();
  });
});

describe('QuizFooter', () => {
  it('renders footer buttons correctly', () => {
    const onPrev = vi.fn();
    const onNextOrSubmit = vi.fn();
    render(
      <QuizFooter 
        isFirst={false}
        isLast={false}
        onPrevious={onPrev}
        onNextOrSubmit={onNextOrSubmit}
        submitting={false}
      />
    );
    
    const prevBtn = screen.getByText('上一题');
    fireEvent.click(prevBtn);
    expect(onPrev).toHaveBeenCalled();

    const nextBtn = screen.getByText('下一题');
    fireEvent.click(nextBtn);
    expect(onNextOrSubmit).toHaveBeenCalled();
  });
});
