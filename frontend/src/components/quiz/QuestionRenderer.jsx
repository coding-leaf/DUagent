import MultiChoiceQuestionCard from './MultiChoiceQuestionCard';
import SingleChoiceQuestionCard from './SingleChoiceQuestionCard';
import UnsupportedQuestionCard from './UnsupportedQuestionCard';

export default function QuestionRenderer({ question, value, onChange }) {
  const normalizedType = String(question?.type || '').toLowerCase();

  if (normalizedType === 'single_choice') {
    return <SingleChoiceQuestionCard question={question} value={value ?? ''} onChange={onChange} />;
  }

  if (normalizedType === 'multi_choice' || normalizedType === 'multiple_choice') {
    return <MultiChoiceQuestionCard question={question} value={value ?? []} onChange={onChange} />;
  }

  return <UnsupportedQuestionCard question={question} />;
}
