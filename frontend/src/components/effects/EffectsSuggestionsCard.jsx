import Icon from '../Icon';
import { parseSummaryText } from '../../utils/summaryParser';

export default function EffectsSuggestionsCard({ summaryText, loading }) {
  const parsed = parseSummaryText(summaryText);

  if (loading) {
    return (
      <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100">
        <p className="font-body-md text-slate-500 leading-relaxed">正在加载建议...</p>
      </div>
    );
  }

  if (!parsed || !parsed.suggestions || parsed.suggestions.length === 0) {
    return null;
  }

  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 w-full">
      <h3 className="font-h3 text-xl font-bold mb-4 flex items-center border-b border-slate-100 pb-3">
        <Icon name="check_circle" className="material-symbols-outlined mr-2 text-emerald-600"/>
        下一步学习建议
      </h3>
      
      {parsed.suggestionsPrefix && (
        <p className="text-sm text-slate-500 mb-4">{parsed.suggestionsPrefix}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {parsed.suggestions.map((item, idx) => (
          <div key={idx} className="bg-white border border-slate-100 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow flex gap-3 items-start">
            <span className="flex items-center justify-center w-6 h-6 bg-emerald-100 text-emerald-800 rounded-full text-xs font-bold flex-shrink-0 mt-0.5">
              {idx + 1}
            </span>
            <div className="min-w-0">
              <div className="text-base font-bold text-slate-800 mb-1.5 break-words">{item.title}</div>
              {item.desc && (
                <div className="text-sm text-slate-500 leading-relaxed break-words">{item.desc}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
