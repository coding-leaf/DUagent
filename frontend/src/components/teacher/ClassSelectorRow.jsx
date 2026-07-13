import Icon from '../Icon';

export default function ClassSelectorRow({ classes, activeClass, setActiveClass, activeClassInfo }) {
  return (
    <section className="mb-6" aria-labelledby="class-selector-title">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 id="class-selector-title" className="text-base font-bold text-slate-900">切换教学班</h2>
          <p className="mt-0.5 text-xs text-slate-500">选择后同步更新学生、资源和班级统计</p>
        </div>
        <span className="hidden text-xs font-medium text-slate-500 sm:block">共 {classes.length} 个教学班</span>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide" role="list">
        {classes.map((cls) => (
          <button
            key={cls.id}
            type="button"
            aria-pressed={activeClass === cls.id}
            onClick={() => setActiveClass(cls.id)}
            className={`min-w-[200px] flex-shrink-0 cursor-pointer rounded-xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-offset-2 ${
              activeClass === cls.id 
                ? 'border-cyan-500 bg-cyan-50 text-cyan-950'
                : 'border-slate-200 bg-white text-slate-800 hover:border-cyan-300 hover:bg-slate-50'
            }`}
          >
            <div className="mb-1 flex items-center justify-between gap-3">
              <span className="truncate text-sm font-bold">{cls.name}</span>
              {activeClass === cls.id && (
                <Icon name="check_circle" className="material-symbols-outlined shrink-0 text-lg text-cyan-600"/>
              )}
            </div>
            <p className="truncate text-xs text-slate-500">{cls.catalog_title || '未绑定资源库'}</p>
            <div className="mt-2 flex items-center gap-3 text-xs font-medium text-slate-600">
              <span>{cls.students ?? 0} 名学生</span>
              {cls.course_code && <span>课程码 {cls.course_code}</span>}
            </div>
          </button>
        ))}
      </div>
      <span className="sr-only">当前教学班：{activeClassInfo?.name || activeClass}</span>
    </section>
  );
}
