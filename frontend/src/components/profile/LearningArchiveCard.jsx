import Icon from '../Icon';

const PROFILE_DIMENSION_LABELS = {
  learning_goal: '当前学习方向',
  weak_points: '待提升内容',
  resource_preference: '学习资料偏好',
  guidance_level: '辅导方式',
  knowledge_progress: '掌握进度',
  discipline: '学习习惯',
  learning_habits: '学习习惯',
};

export default function LearningArchiveCard({
  handleProfileRefresh,
  refreshing,
  refreshMessage,
  refreshError,
  profile_dimensions,
  formatDimensionValue,
  sourceLabel
}) {
  return (
    <section className="lg:col-span-7 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
      <div className="flex items-center justify-between gap-4 mb-5">
        <div>
          <h3 className="font-h3 text-xl flex items-center gap-2 text-on-surface">
            <Icon name="badge" className="material-symbols-outlined text-cyan-500"/> 学习档案
          </h3>
          <p className="text-sm text-secondary mt-1">根据学习行为、评测结果和个人补充生成的课程学习档案。</p>
        </div>
        <button
          onClick={handleProfileRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-600 text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-700 transition-colors"
        >
          <Icon name={refreshing ? 'progress_activity' : 'sync'} className={`material-symbols-outlined text-base ${refreshing ? 'animate-spin' : ''}`}/>
          {refreshing ? '同步中...' : '同步画像'}
        </button>
      </div>
      {(refreshMessage || refreshError) && (
        <div className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
          refreshError
            ? 'border-red-100 bg-red-50 text-red-600'
            : 'border-cyan-100 bg-cyan-50 text-cyan-700'
        }`}>
          {refreshError || refreshMessage}
        </div>
      )}
      {profile_dimensions?.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {profile_dimensions.map((dimension) => (
            <div key={dimension.key} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3 mb-2">
                <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">
                  {PROFILE_DIMENSION_LABELS[dimension.key] || dimension.label}
                </p>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white text-cyan-700 border border-cyan-100">
                  {sourceLabel(dimension.source)}
                </span>
              </div>
              <p className="text-sm text-on-surface font-semibold leading-6">
                {formatDimensionValue(dimension.value, dimension.key)}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate-400 py-6 text-center">暂无画像维度数据</p>
      )}
    </section>
  );
}
