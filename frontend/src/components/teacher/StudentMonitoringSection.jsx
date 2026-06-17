import Icon from '../Icon';
import FeedbackStatus from '../FeedbackStatus';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';

export default function StudentMonitoringSection({
  activeClassInfo,
  activeClass,
  studentsLoading,
  studentsError,
  students,
  navigate
}) {
  return (
    <section className="mb-margin">
      <div className="bg-white rounded-xl border border-outline-variant shadow-sm overflow-hidden">
        <div className="px-md py-4 border-b border-outline-variant flex justify-between items-center bg-surface-container-lowest">
          <div className="flex items-center gap-2">
            <Icon name="monitoring" className="material-symbols-outlined text-primary"/>
            <h3 className="font-h3 text-xl text-on-surface">{activeClassInfo?.name || activeClass} 学生实时监控</h3>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center bg-surface-container-low rounded-lg px-3 py-1.5 border border-outline-variant">
              <Icon name="search" className="material-symbols-outlined text-outline text-sm mr-2"/>
              <input className="bg-transparent border-none focus:ring-0 text-sm w-32 outline-none" placeholder="搜索学生..." type="text" />
            </div>
            <button className="p-2 rounded-lg hover:bg-surface-container transition-colors">
              <Icon name="refresh" className="material-symbols-outlined text-outline"/>
            </button>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-gutter gap-y-4 p-md">
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
                <div
                  key={student.user_id}
                  data-testid="student-card"
                  onClick={() => navigate(`/teacher/report?course_id=${activeClass}&student_id=${student.user_id}`)}
                  className="flex items-center gap-6 p-4 rounded-xl border border-outline-variant hover:bg-surface-container-low transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-3 w-48">
                    <div className={`w-9 h-9 ${student.avatar_color} rounded-full flex items-center justify-center font-bold`}>
                      {student.avatar_text}
                    </div>
                    <div>
                      <p className="font-label-sm text-on-surface">{student.username} ({student.english_name})</p>
                      <p className="text-[10px] text-outline">ID: {student.student_id}</p>
                    </div>
                  </div>
                  {useMock ? (
                    <>
                      <div className="w-32">
                        <span className="px-2.5 py-1 bg-surface-container text-on-surface-variant text-[11px] font-medium rounded border border-outline-variant/30">
                          {student.current_path_node}
                        </span>
                      </div>
                      <div className="flex-1 flex items-center gap-3">
                        <div className="flex-1 bg-surface-container-highest h-1.5 rounded-full overflow-hidden">
                          <div className="bg-primary h-full" style={{ width: `${student.overall_mastery * 100}%` }}></div>
                        </div>
                        <span className="text-xs font-bold text-on-surface">{Math.round(student.overall_mastery * 100)}%</span>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="w-32">
                        <span className="text-xs text-outline font-medium truncate block max-w-[120px]">
                          {student.major || '—'}
                        </span>
                      </div>
                      <div className="flex-1 text-right">
                        <span className="px-2.5 py-1 bg-slate-100 text-slate-600 text-xs rounded border border-outline-variant/20">
                          {student.grade || '—'}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Pagination */}
        <div className="px-md py-4 bg-surface-container-low border-t border-outline-variant flex justify-between items-center">
          <span className="text-xs font-medium text-outline">当前显示 {activeClassInfo?.name || activeClass} (42名学生中展示 14名)</span>
          <div className="flex gap-1">
            <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">上一页</button>
            <button className="px-3 py-1 bg-primary text-white border border-primary rounded-lg text-xs font-bold">1</button>
            <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">2</button>
            <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">下一页</button>
          </div>
        </div>
      </div>
    </section>
  );
}
