import Icon from '../Icon';
import FeedbackStatus from '../FeedbackStatus';

export default function StudentMonitoringSection({
  activeClassInfo,
  activeClass,
  studentsLoading,
  studentsError,
  students,
  isMockMode,
  totalStudents,
  currentPage,
  totalPages,
  onPageChange,
  searchQuery,
  onSearchChange,
  onRefresh,
  onStudentClick
}) {
  return (
    <section className="mb-8" aria-labelledby="student-list-title">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 border-b border-slate-200 bg-white px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
              <Icon name="groups" className="material-symbols-outlined"/>
            </span>
            <div>
              <h2 id="student-list-title" className="text-xl font-bold text-slate-900">学生学情与名单</h2>
              <p className="mt-0.5 text-xs text-slate-500">{activeClassInfo?.name || activeClass} · 共 {totalStudents} 名学生</p>
            </div>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <label className="flex min-w-0 flex-1 items-center rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 sm:w-56">
              <Icon name="search" className="material-symbols-outlined mr-2 text-sm text-slate-500"/>
              <input 
                aria-label="搜索学生"
                className="min-w-0 flex-1 border-none bg-transparent text-sm outline-none"
                placeholder="搜索学生..." 
                type="text" 
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
              />
            </label>
            <button onClick={onRefresh} className="flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-cyan-300 hover:text-cyan-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500">
              <Icon name="refresh" className="material-symbols-outlined"/>
              <span className="hidden sm:inline">刷新</span>
            </button>
          </div>
        </div>
        
        <div className="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2 lg:p-5">
            {studentsLoading ? (
              <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                <FeedbackStatus status="loading" title="加载学生列表..." />
              </div>
            ) : studentsError ? (
              <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                <FeedbackStatus status="error" title={studentsError} />
              </div>
            ) : students.length === 0 ? (
              <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
                <FeedbackStatus status="empty" title="该班级暂无学生" />
              </div>
            ) : (
              students.map(student => (
                <button
                  type="button"
                  key={student.user_id}
                  data-testid="student-card"
                  onClick={() => onStudentClick(student.user_id)}
                  className="flex w-full cursor-pointer items-center gap-3 rounded-xl border border-slate-200 p-4 text-left transition-colors hover:border-cyan-300 hover:bg-cyan-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                >
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-bold ${student.avatar_color}`}>
                      {student.avatar_text}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-slate-900">{student.username}{student.english_name ? ` (${student.english_name})` : ''}</p>
                    <p className="mt-0.5 text-xs text-slate-500">学号：{student.student_id || '—'}</p>
                  </div>
                  {isMockMode ? (
                    <div className="hidden min-w-40 sm:block">
                        <span className="text-xs font-medium text-slate-600">
                          {student.current_path_node}
                        </span>
                      <div className="mt-2 flex items-center gap-2">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                          <div className="bg-primary h-full" style={{ width: `${student.overall_mastery * 100}%` }}></div>
                        </div>
                        <span className="text-xs font-bold text-slate-700">{Math.round(student.overall_mastery * 100)}%</span>
                      </div>
                    </div>
                  ) : (
                    <div className="hidden items-center gap-2 sm:flex">
                      <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{student.major || '专业未填写'}</span>
                      <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{student.grade || '年级未填写'}</span>
                    </div>
                  )}
                  <Icon name="chevron_right" className="material-symbols-outlined shrink-0 text-slate-400" />
                </button>
              ))
            )}
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs font-medium text-slate-500">
            第 {currentPage}/{totalPages} 页 · 共 {totalStudents} 名学生
          </span>
          <div className="flex gap-1">
            <button 
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="cursor-pointer rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              上一页
            </button>
            <button 
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="cursor-pointer rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
