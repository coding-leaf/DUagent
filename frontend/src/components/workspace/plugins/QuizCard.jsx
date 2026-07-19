import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function QuizCard({ question, choices, correctAnswer, course_id, question_ids }) {
  const navigate = useNavigate();
  const [selected, setSelected] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  if (course_id && Array.isArray(question_ids) && question_ids.length > 0) {
    const startPractice = () => {
      const params = new URLSearchParams({
        course_id,
        source: 'personalized',
        question_ids: question_ids.join(','),
      });
      navigate(`/quiz?${params.toString()}`);
    };
    return (
      <div className="bg-white border border-cyan-200 rounded-2xl p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-slate-800 font-semibold text-[15px]">私有选择题练习已生成</h3>
            <p className="text-sm text-slate-500 mt-2">共 {question_ids.length} 题，作答结果会进入学习证据。</p>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-cyan-50 text-cyan-700 text-xs font-medium">仅自己可见</span>
        </div>
        <button
          onClick={startPractice}
          className="mt-5 w-full px-4 py-2.5 bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer"
        >
          开始练习
        </button>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <h3 className="text-slate-800 font-semibold mb-4 text-[15px]">{question}</h3>
      <div className="space-y-2">
        {choices?.map((choice, idx) => {
          let optionStyle = 'border-slate-200 hover:bg-slate-50 text-slate-700';
          let accessibilityText = '';

          if (submitted) {
            if (idx === correctAnswer) {
              optionStyle = 'bg-green-50 border-green-300 text-green-800';
              accessibilityText = ' (正确答案)';
            } else if (selected === idx) {
              optionStyle = 'bg-red-50 border-red-300 text-red-800';
              accessibilityText = ' (回答错误)';
            }
          } else if (selected === idx) {
            optionStyle = 'bg-cyan-50 border-cyan-400 text-cyan-800';
          }
          return (
            <button
              key={idx}
              disabled={submitted}
              onClick={() => setSelected(idx)}
              className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-all cursor-pointer ${optionStyle}`}
            >
              {choice}{accessibilityText}
            </button>
          );
        })}
      </div>
      <div className="mt-4 flex justify-end">
        <button
          disabled={selected === null || submitted}
          onClick={() => setSubmitted(true)}
          className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer"
        >
          提交答案
        </button>
      </div>
    </div>
  );
}
