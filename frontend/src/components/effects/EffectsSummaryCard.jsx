import Icon from '../Icon';
import MarkdownViewer from '../common/MarkdownViewer';

export default function EffectsSummaryCard({ summaryText, loading, onGenerateResources }) {
  return (
    <div className="bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 h-full flex flex-col justify-start">
      <h3 className="font-h3 text-xl font-bold mb-3 flex items-center">
        <Icon name="psychology" className="material-symbols-outlined mr-2 text-cyan-600"/>
        学习效果总结
      </h3>
      {loading ? (
        <p className="font-body-md text-slate-500 leading-relaxed">正在加载学习效果...</p>
      ) : summaryText ? (
        <MarkdownViewer content={summaryText} className="text-slate-600 text-body-md" />
      ) : (
        <p className="font-body-md text-slate-500 leading-relaxed">
          暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
        </p>
      )}
      {!loading && summaryText && onGenerateResources && (
        <button
          type="button"
          onClick={onGenerateResources}
          className="mt-5 flex w-fit items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700"
        >
          <Icon name="auto_awesome" className="material-symbols-outlined text-[18px]" />
          根据学情生成资料
        </button>
      )}
    </div>
  );
}
