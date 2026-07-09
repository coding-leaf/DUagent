import Icon from '../Icon';
import { parseSummaryText } from '../../utils/summaryParser';

export default function EffectsSummaryCard({ summaryText, loading }) {
  const parsed = parseSummaryText(summaryText);

  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
      <h3 className="font-h3 text-xl font-bold mb-4 flex items-center border-b border-slate-100 pb-3">
        <Icon name="psychology" className="material-symbols-outlined mr-2 text-cyan-600"/>
        学习效果总结
      </h3>
      
      {loading ? (
        <p className="font-body-md text-slate-500 leading-relaxed">正在加载学习效果...</p>
      ) : parsed ? (
        <div className="flex flex-col lg:flex-row gap-6 w-full">
          {/* Left Column: Diagnostics (Responsive sub-grid) */}
          <div className="flex-1 lg:flex-[1.6] grid grid-cols-1 sm:grid-cols-2 gap-4 content-start">
            {parsed.scope && (
              <div className="p-4 bg-cyan-50/50 border border-cyan-100 rounded-lg">
                <h4 className="font-bold text-sm text-cyan-800 flex items-center mb-1">
                  <Icon name="menu_book" className="material-symbols-outlined text-base mr-1.5" />
                  学习范围
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">{parsed.scope}</p>
              </div>
            )}

            {parsed.mastery && (
              <div className="p-4 bg-red-50/50 border border-red-100 rounded-lg">
                <h4 className="font-bold text-sm text-red-800 flex items-center mb-1">
                  <Icon name="analytics" className="material-symbols-outlined text-base mr-1.5" />
                  当前掌握
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">{parsed.mastery}</p>
              </div>
            )}

            {parsed.behavior && (
              <div className="p-4 bg-slate-50/80 border border-slate-100 rounded-lg sm:col-span-2">
                <h4 className="font-bold text-sm text-slate-700 flex items-center mb-1">
                  <Icon name="insights" className="material-symbols-outlined text-base mr-1.5" />
                  学习行为
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed">{parsed.behavior}</p>
              </div>
            )}
          </div>

          {/* Right Column: Recommendations */}
          {parsed.suggestions && parsed.suggestions.length > 0 && (
            <div className="flex-1 bg-slate-50/40 border border-dashed border-slate-200 rounded-xl p-5">
              <h4 className="font-bold text-base text-emerald-800 flex items-center mb-3">
                <Icon name="check_circle" className="material-symbols-outlined text-emerald-600 mr-2" />
                下一步学习建议
              </h4>
              
              {parsed.suggestionsPrefix && (
                <p className="text-xs text-slate-400 mb-3">{parsed.suggestionsPrefix}</p>
              )}

              <div className="space-y-3">
                {parsed.suggestions.map((item, idx) => (
                  <div key={idx} className="bg-white border border-gray-100 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow">
                    <div className="flex gap-2.5 items-start">
                      <span className="flex items-center justify-center w-5 h-5 bg-emerald-100 text-emerald-800 rounded-full text-xs font-bold flex-shrink-0 mt-0.5">
                        {idx + 1}
                      </span>
                      <div>
                        <div className="text-sm font-bold text-slate-800 mb-1">{item.title}</div>
                        {item.desc && (
                          <div className="text-xs text-slate-500 leading-relaxed">{item.desc}</div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <p className="font-body-md text-slate-500 leading-relaxed">
          暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
        </p>
      )}
    </div>
  );
}
