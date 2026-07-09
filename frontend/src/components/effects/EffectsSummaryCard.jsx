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
        <div className="w-full">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 content-start">
            {parsed.scope && (
              <div className="p-5 bg-cyan-50/50 border border-cyan-100 rounded-lg">
                <h4 className="font-bold text-sm text-cyan-800 flex items-center mb-1.5">
                  <Icon name="menu_book" className="material-symbols-outlined text-base mr-1.5" />
                  学习范围
                </h4>
                <p className="text-sm text-slate-700 leading-relaxed">{parsed.scope}</p>
              </div>
            )}

            {parsed.mastery && (
              <div className="p-5 bg-red-50/50 border border-red-100 rounded-lg">
                <h4 className="font-bold text-sm text-red-800 flex items-center mb-1.5">
                  <Icon name="analytics" className="material-symbols-outlined text-base mr-1.5" />
                  当前掌握
                </h4>
                <p className="text-sm text-slate-700 leading-relaxed">{parsed.mastery}</p>
              </div>
            )}

            {parsed.behavior && (
              <div className="p-5 bg-slate-50/80 border border-slate-100 rounded-lg sm:col-span-2">
                <h4 className="font-bold text-sm text-slate-700 flex items-center mb-1.5">
                  <Icon name="insights" className="material-symbols-outlined text-base mr-1.5" />
                  学习行为
                </h4>
                <p className="text-sm text-slate-700 leading-relaxed">{parsed.behavior}</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="font-body-md text-slate-500 leading-relaxed">
          暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
        </p>
      )}
    </div>
  );
}
