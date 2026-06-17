import Icon from '../Icon';

export default function EffectsSummaryCard({ summaryText, loading }) {
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
      <h3 className="font-h3 text-xl font-bold mb-3 flex items-center">
        <Icon name="psychology" className="material-symbols-outlined mr-2 text-cyan-600"/>
        学习效果总结
      </h3>
      {loading ? (
        <p className="font-body-md text-slate-500 leading-relaxed">正在加载学习效果...</p>
      ) : summaryText ? (
        <p className="font-body-md text-slate-600 leading-relaxed">{summaryText}</p>
      ) : (
        <p className="font-body-md text-slate-500 leading-relaxed">
          暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
        </p>
      )}
    </div>
  );
}
