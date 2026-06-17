export default function ProfileBanner({ report, classId }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm flex flex-col md:flex-row items-center gap-6">
      <div className="w-20 h-20 rounded-full overflow-hidden bg-cyan-500/10 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-3xl flex-shrink-0">
        {(report?.student?.real_name || report?.student?.student_id || '学').charAt(0)}
      </div>
      <div className="flex-grow text-center md:text-left">
        <h2 className="text-2xl font-bold text-on-surface mb-1">{report?.student?.real_name || report?.student?.student_id || '学生'}</h2>
        <p className="text-sm text-secondary">学号: {report?.student?.student_id || '未知'} · 班级ID: {classId}</p>
      </div>
      <div className="bg-primary/5 border border-primary/20 rounded-xl px-6 py-4 flex flex-col items-center">
        <span className="text-2xl font-black text-primary">待定</span>
        <span className="text-[10px] text-secondary font-bold uppercase tracking-wider">评分口径待定</span>
      </div>
    </div>
  );
}
