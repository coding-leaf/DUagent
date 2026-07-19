import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import QuizHeader from '../QuizHeader';
import QuizProgressCard from '../QuizProgressCard';
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
        courseName="Test Course" 
        currentKnowledgePoint="Test Knowledge"
        onExit={onExit} 
      />
    );
    expect(screen.getByText('Test Course')).toBeInTheDocument();
    expect(screen.getByText('Test Knowledge')).toBeInTheDocument();
    expect(screen.queryByTestId('icon-analytics')).not.toBeInTheDocument();
    expect(screen.queryByTestId('icon-notifications')).not.toBeInTheDocument();
    expect(screen.queryByRole('img', { name: '用户头像' })).not.toBeInTheDocument();
    
    // Simulate exit click
    fireEvent.click(screen.getByTitle(/返回上一页/i));
    expect(onExit).toHaveBeenCalled();
  });
});

describe('QuizSidebar', () => {
  it('renders metadata', () => {
    render(
      <QuizSidebar 
        currentChapter="Test Chapter"
        sourceLabel="Test Source"
        difficulty="hard"
        knowledgePoint="Test Knowledge"
        questionTypeLabel="Single Choice"
      />
    );
    expect(screen.getByText('Test Chapter')).toBeInTheDocument();
    expect(screen.getByText('Test Source')).toBeInTheDocument();
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
        hasAnsweredCurrent={true}
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

describe('QuizProgressCard', () => {
  it('renders progress text and bar correctly', () => {
    render(
      <QuizProgressCard 
        currentQuestionIndex={2} 
        totalQuestions={10} 
      />
    );
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('/ 10 题')).toBeInTheDocument();
    expect(screen.getByText('完成进度 30%')).toBeInTheDocument();
  });
});
