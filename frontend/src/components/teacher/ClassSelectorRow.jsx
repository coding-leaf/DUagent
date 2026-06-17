import Icon from '../Icon';

export default function ClassSelectorRow({ classes, activeClass, setActiveClass, activeClassInfo }) {
  return (
    <section className="mb-margin">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-h3 text-xl text-on-surface">教学班选择</h3>
        <span className="text-sm text-outline">当前：{activeClassInfo?.name || activeClass}</span>
      </div>
      <div className="flex gap-gutter overflow-x-auto pb-2 scrollbar-hide">
        {classes.map((cls) => (
          <button
            key={cls.id}
            onClick={() => setActiveClass(cls.id)}
            className={`min-w-[240px] flex-shrink-0 bg-white rounded-xl p-md text-left transition-all ${
              activeClass === cls.id 
                ? 'border-2 border-primary shadow-md ring-4 ring-primary/10' 
                : 'border border-outline-variant hover:border-primary/50 hover:shadow-lg'
            }`}
          >
            <div className="flex justify-between items-center mb-2">
              <span className={`text-xs font-bold uppercase ${activeClass === cls.id ? 'text-primary' : 'text-outline'}`}>
                {cls.name}
              </span>
              {activeClass === cls.id && (
                <Icon name="check_circle" className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: '"FILL" 1' }}/>
              )}
            </div>
            <p className="font-h3 text-lg text-on-surface mb-1">{cls.topic}</p>
            {cls.catalog_title && (
              <p className="text-xs text-outline mb-1 line-clamp-1">资源库：{cls.catalog_title}</p>
            )}
            {cls.course_code && (
              <p className="text-xs font-medium text-cyan-700 mb-1">课程码：{cls.course_code}</p>
            )}
            <p className="text-sm text-outline">{cls.students} 名学生</p>
          </button>
        ))}
      </div>
    </section>
  );
}
