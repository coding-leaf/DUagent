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

export default function MultiChoiceQuestionCard({ question, value = [], onChange }) {
  const options = Array.isArray(question?.options) ? question.options.map(normalizeOption) : [];
  const selectedValues = Array.isArray(value) ? value : [];

  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-amber-50 px-4 py-3 text-xs text-amber-700">
        多选题可选择多个答案。
      </div>
      {options.map((option) => {
        const isSelected = selectedValues.includes(option.key);
        return (
          <label
            key={option.key}
            className={`group flex items-center p-5 rounded-xl border-2 transition-all cursor-pointer ${
              isSelected ? 'border-primary bg-primary/5' : 'border-slate-200 hover:border-primary hover:bg-primary/5'
            }`}
          >
            <input
              className="w-5 h-5 text-primary border-slate-300 rounded focus:ring-primary"
              type="checkbox"
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
