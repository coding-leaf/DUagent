

export default function TrainingReportModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-md backdrop-blur-overlay">
      <div className="w-full max-w-[960px] bg-white rounded-[24px] shadow-[0px_8px_40px_rgba(0,0,0,0.08)] overflow-hidden flex flex-col max-h-[90vh] text-left">
        {/* Modal Header */}
        <div className="px-xl pt-lg pb-md flex justify-between items-end border-b border-surface-container">
          <div>
            <h2 className="font-h2 text-2xl text-on-surface mb-xs font-bold">训练完成</h2>
            <p className="font-body-md text-secondary text-sm">第4章：树形结构 - 平衡二叉树专项练习</p>
          </div>
          <div className="text-right">
            <span className="font-label-sm text-xs text-primary uppercase tracking-widest bg-primary-container/10 px-3 py-1 rounded-full font-bold">Practice Report</span>
          </div>
        </div>

        {/* Modal Content Scroll Area */}
        <div className="flex-1 overflow-y-auto px-xl py-md custom-scrollbar">
          {/* Performance Overview Grid */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-md mb-lg items-stretch">
            {/* Accuracy Score */}
            <div className="md:col-span-4 bg-surface-container-low p-md rounded-xl flex flex-col items-center justify-center text-center">
              <span className="font-label-sm text-secondary mb-base text-xs font-bold">正确率</span>
              <div className="relative flex items-center justify-center h-24 w-24">
                <svg className="absolute inset-0 h-24 w-24 transform -rotate-90">
                  <circle className="text-surface-container-highest" cx="48" cy="48" fill="transparent" r="40" stroke="currentColor" strokeWidth="8"></circle>
                  <circle className="text-primary-container" cx="48" cy="48" fill="transparent" r="40" stroke="currentColor" strokeDasharray="251.2" strokeDashoffset="25.12" strokeWidth="8"></circle>
                </svg>
                <span className="text-2xl font-bold text-on-surface">90%</span>
              </div>
              <span className="mt-2 px-2 py-0.5 bg-error text-white text-[10px] font-bold rounded-full uppercase tracking-tighter shadow-sm">新纪录</span>
            </div>

            {/* Time & Rank */}
            <div className="md:col-span-8 grid grid-cols-1 sm:grid-cols-2 gap-md">
              <div className="bg-white border border-outline-variant p-md rounded-xl flex items-center gap-md">
                <div className="h-12 w-12 bg-primary-container/10 rounded-full flex items-center justify-center text-primary-container flex-shrink-0">
                  <span className="material-symbols-outlined">timer</span>
                </div>
                <div>
                  <span className="block font-label-sm text-secondary text-xs">练习耗时</span>
                  <span className="text-xl font-bold text-on-surface">14:22</span>
                </div>
              </div>
              <div className="bg-white border border-outline-variant p-md rounded-xl flex items-center gap-md">
                <div className="h-12 w-12 bg-tertiary-container/20 rounded-full flex items-center justify-center text-tertiary flex-shrink-0">
                  <span className="material-symbols-outlined">trending_up</span>
                </div>
                <div>
                  <span className="block font-label-sm text-secondary text-xs">历史击败</span>
                  <span className="text-xl font-bold text-on-surface">86% 用户</span>
                </div>
              </div>
            </div>

            {/* AI Intelligence Advice */}
            <div className="md:col-span-12 bg-surface-container-lowest border-2 border-primary-container/20 p-md rounded-2xl relative overflow-hidden flex items-center shadow-sm">
              <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                <span className="material-symbols-outlined text-[80px]">psychology</span>
              </div>
              <div className="flex gap-md w-full items-start">
                <div className="flex-shrink-0 h-12 w-12 rounded-xl bg-primary-container flex items-center justify-center text-white shadow-lg">
                  <span className="material-symbols-outlined">smart_toy</span>
                </div>
                <div className="flex-1">
                  <h4 className="font-body-lg font-bold text-on-surface mb-1">AI 智能教练建议</h4>
                  <p className="font-body-md text-on-surface-variant leading-relaxed text-sm">
                    总体表现优异！你在<span className="text-primary font-bold">二叉树的基本计算</span>上非常熟练。然而，在处理<span className="text-error font-bold">AVL树的平衡旋转</span>逻辑时，你的决策时间比平均水平长了 18%，建议针对“双旋转（LR/RL）”场景进行强化训练。
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Detailed Analysis List */}
          <div className="space-y-sm">
            <h4 className="font-label-sm text-secondary uppercase mb-base text-xs font-bold">详细解析回顾</h4>
            
            {/* Analysis Item 1 (Correct) */}
            <div className="group flex items-center gap-md p-md bg-white border border-outline-variant rounded-xl hover:border-primary-container transition-all cursor-pointer">
              <div className="flex-shrink-0 h-10 w-10 rounded-full bg-green-50 text-green-600 flex items-center justify-center font-bold">1</div>
              <div className="flex-1 min-w-0">
                <h5 className="font-body-md font-medium text-on-surface truncate text-sm">二叉树遍历序列还原算法复杂度分析</h5>
                <div className="flex gap-sm mt-1">
                  <span className="font-label-sm text-[11px] text-secondary flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">bolt</span> 快速通过
                  </span>
                  <span className="font-label-sm text-[11px] text-green-600 font-bold">正确</span>
                </div>
              </div>
              <span className="material-symbols-outlined text-secondary opacity-0 group-hover:opacity-100 transition-opacity">chevron_right</span>
            </div>

            {/* Analysis Item 2 (Wrong) */}
            <div className="group flex items-center gap-md p-md bg-white border border-error/20 rounded-xl hover:border-error transition-all cursor-pointer">
              <div className="flex-shrink-0 h-10 w-10 rounded-full bg-error-container text-error flex items-center justify-center font-bold">2</div>
              <div className="flex-1 min-w-0">
                <h5 className="font-body-md font-medium text-on-surface truncate text-sm">平衡二叉树在插入节点后的旋转逻辑判断</h5>
                <div className="flex gap-sm mt-1">
                  <span className="font-label-sm text-[11px] text-secondary flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">timer</span> 耗时 4:12
                  </span>
                  <span className="font-label-sm text-[11px] text-error font-bold">错误</span>
                </div>
              </div>
              <span className="material-symbols-outlined text-secondary opacity-0 group-hover:opacity-100 transition-opacity">chevron_right</span>
            </div>

            {/* Analysis Item 3 (Correct) */}
            <div className="group flex items-center gap-md p-md bg-white border border-outline-variant rounded-xl hover:border-primary-container transition-all cursor-pointer">
              <div className="flex-shrink-0 h-10 w-10 rounded-full bg-green-50 text-green-600 flex items-center justify-center font-bold">3</div>
              <div className="flex-1 min-w-0">
                <h5 className="font-body-md font-medium text-on-surface truncate text-sm">完全二叉树的父子节点索引关系推导</h5>
                <div className="flex gap-sm mt-1">
                  <span className="font-label-sm text-[11px] text-secondary flex items-center gap-1">
                    <span className="material-symbols-outlined text-[14px]">bolt</span> 快速通过
                  </span>
                  <span className="font-label-sm text-[11px] text-green-600 font-bold">正确</span>
                </div>
              </div>
              <span className="material-symbols-outlined text-secondary opacity-0 group-hover:opacity-100 transition-opacity">chevron_right</span>
            </div>
          </div>
        </div>

        {/* Modal Footer (Actions) */}
        <div className="px-xl py-lg bg-surface-container-low border-t border-surface-container flex gap-md justify-center">
          <button
            onClick={onClose}
            className="flex-1 max-w-[200px] h-12 rounded-xl border-2 border-primary-container text-primary font-bold hover:bg-primary-container/5 active:scale-95 transition-all flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined">home</span>
            返回主页
          </button>
          <button
            onClick={onClose}
            className="flex-1 max-w-[200px] h-12 rounded-xl bg-primary-container text-white font-bold shadow-lg shadow-primary-container/20 hover:brightness-110 active:scale-95 transition-all flex items-center justify-center gap-2"
          >
            下一组练习
            <span className="material-symbols-outlined">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
  );
}
