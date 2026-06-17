import Icon from '../Icon';

export default function ProfileHeaderCard({
  displayInitial,
  displayName,
  discipline_badge,
  disciplineBadgeView,
  currentCourseName,
  profileFields,
}) {
  return (
    <div className="relative overflow-hidden bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-8 mb-8">
      <div className="absolute top-0 right-0 w-64 h-64 -mr-20 -mt-20 opacity-5">
        <Icon name="school" className="material-symbols-outlined text-9xl"/>
      </div>
      <div className="relative">
        <div className="relative w-32 h-32 rounded-full border-4 border-slate-100 overflow-hidden bg-cyan-500/10">
          <div className="w-full h-full rounded-full bg-cyan-500/20 text-cyan-600 flex items-center justify-center font-bold text-xl">
            {displayInitial}
          </div>
        </div>
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-4 mb-2">
          <h1 className="font-h1 text-3xl text-on-surface">{displayName}</h1>
          {discipline_badge?.level ? (
            <span className="bg-amber-50 text-amber-700 text-xs px-4 py-1 rounded-full font-bold uppercase tracking-wider border border-amber-200">
              学科勋章：{disciplineBadgeView?.subject ? `${disciplineBadgeView.subject} · ` : ''}{disciplineBadgeView?.level}
            </span>
          ) : (
            <span className="bg-slate-100 text-slate-400 text-xs px-4 py-1 rounded-full">学科勋章：—</span>
          )}
        </div>
        <p className="text-body-md text-secondary">当前进修课程：<span className="text-primary font-bold">{currentCourseName}</span></p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
          {profileFields?.map((field) => (
            <div key={field.label} className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
              <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{field.label}</p>
              <p className="text-sm text-on-surface font-semibold truncate">{field.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
