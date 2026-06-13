const normalizeOption = (option, index) => {
  if (option && typeof option === 'object') {
    return {
      key: option.key ?? String.fromCharCode(65 + index),
      text: option.text ?? option.label ?? String(option.key ?? ''),
    };
  }

  const key = String.fromCharCode(65 + index);
  return { key, text: String(option ?? '') };
};

export default function SingleChoiceQuestionCard({ question, value, onChange }) {
  const options = Array.isArray(question?.options) ? question.options.map(normalizeOption) : [];

  return (
    <div className="space-y-4">
      {options.map((option) => {
        const isSelected = value === option.key;
        return (
          <label
            key={option.key}
            className={`group flex items-center p-5 rounded-xl border-2 transition-all cursor-pointer ${
              isSelected ? 'border-primary bg-primary/5' : 'border-slate-200 hover:border-primary hover:bg-primary/5'
            }`}
          >
            <input
              className="w-5 h-5 text-primary border-slate-300 focus:ring-primary"
              name={`question-${question.id}`}
              type="radio"
              checked={isSelected}
              onChange={() => onChange(option.key)}
            />
            <span className={`ml-4 font-body-md transition-colors ${
              isSelected ? 'text-primary font-bold' : 'text-on-surface group-hover:text-primary'
            }`}>
              {option.key}. {option.text}
            </span>
          </label>
        );
      })}
    </div>
  );
}
