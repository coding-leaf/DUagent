import { useState } from 'react';

export default function QuizCard({ question, choices, correctAnswer }) {
  const [selected, setSelected] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <h3 className="text-slate-800 font-semibold mb-4 text-[15px]">{question}</h3>
      <div className="space-y-2">
        {choices?.map((choice, idx) => {
          let optionStyle = 'border-slate-200 hover:bg-slate-50 text-slate-700';
          if (submitted) {
            if (idx === correctAnswer) optionStyle = 'bg-green-50 border-green-300 text-green-800';
            else if (selected === idx) optionStyle = 'bg-red-50 border-red-300 text-red-800';
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
              {choice}
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
