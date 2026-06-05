export default function FeedbackStatus({ status, title, description, onRetry }) {
  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center w-[min(92vw,24rem)] min-w-[18rem] box-border">
        <span className="material-symbols-outlined animate-spin text-primary text-4xl mb-4">
          progress_activity
        </span>
        <h4 className="text-lg font-bold text-on-surface mb-2 whitespace-nowrap">{title || '加载中...'}</h4>
        {description && <p className="text-sm text-secondary max-w-sm whitespace-normal break-words">{description}</p>}
      </div>
    );
  }

  if (status === 'empty') {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center w-[min(92vw,24rem)] min-w-[18rem] box-border border border-dashed border-outline-variant rounded-2xl bg-surface-container-lowest">
        <span className="material-symbols-outlined text-outline text-5xl mb-4">
          folder_open
        </span>
        <h4 className="text-lg font-bold text-on-surface mb-2 whitespace-nowrap">{title || '暂无数据'}</h4>
        {description && <p className="text-sm text-secondary max-w-sm mb-4">{description}</p>}
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center w-[min(92vw,24rem)] min-w-[18rem] box-border border border-error-container/30 rounded-2xl bg-error-container/5">
        <span className="material-symbols-outlined text-error text-5xl mb-4">
          error
        </span>
        <h4 className="text-lg font-bold text-error mb-2">{title || '加载失败'}</h4>
        <p className="text-sm text-secondary max-w-sm mb-6">{description || '请检查您的网络连接或稍后重试。'}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-6 py-2.5 bg-error text-white font-bold rounded-xl shadow-md hover:bg-error-variant transition-all active:scale-95 cursor-pointer flex items-center gap-2"
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
            重新加载
          </button>
        )}
      </div>
    );
  }

  return null;
}
