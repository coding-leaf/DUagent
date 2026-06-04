import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { teachingService } from '../api/services/teaching';

export default function TeacherConsole() {
  const navigate = useNavigate();
  const [activeClass, setActiveClass] = useState(null);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);

  // 获取班级列表
  useEffect(() => {
    teachingService.getClasses().then(res => {
      if (res.code === 200 && res.data.length > 0) {
        setClasses(res.data);
        setActiveClass(res.data[0].id);
      }
    }).catch(console.error);
  }, []);

  // 当选择的班级改变时，获取学生列表和AI洞察
  useEffect(() => {
    if (activeClass) {
      setTimeout(() => setLoading(true), 0);
      Promise.all([
        teachingService.getClassStudents(activeClass),
        teachingService.getConsoleInsights(activeClass)
      ]).then(([studentsRes, insightsRes]) => {
        if (studentsRes.code === 200) setStudents(studentsRes.data);
        if (insightsRes.code === 200) setInsights(insightsRes.data);
      }).catch(console.error).finally(() => setLoading(false));
    }
  }, [activeClass]);

  return (
    <div className="min-h-screen flex flex-col bg-background text-on-background font-body-md">
      {/* Top Header */}
      <header className="fixed top-0 w-full z-50 flex justify-between items-center px-gutter h-20 bg-white border-b border-outline-variant shadow-sm font-['Public_Sans'] antialiased">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold tracking-tight text-on-surface">数据结构 (Data Structures)</h1>
          <span className="px-2 py-1 bg-surface-container-high text-primary font-bold text-xs rounded uppercase">教学控制台</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-slate-200 overflow-hidden border border-outline-variant">
              <img alt="Teacher Profile" className="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBEmN6iPeykBJM4g-FxZGQKujWsCGE-ECZSb2n7Om_izFEwlflhnVLi8aiRkOPALKmOqmYspwDxQXhjRwpKinCsHeX82NYknLqB_BawjcrrG_R6fLceDe8E-djpgDunaUfMKNUpTMvJLEglTno8tbrwrX-u5ZbtloceQzZNyT3tUP1_YmA6sL8f0Py7ra53pu1vfMKFX-rn8TRIvfzsTB_Q-Pgp0_gVgYl-Cff4Cg2VxJf1eYU35oScr-WfgA0scltfK38DvdpCbyzX" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-on-surface">Prof. Zhang</span>
              <span className="text-[10px] text-outline uppercase tracking-wider">系统管理员</span>
            </div>
          </div>
          <div className="h-8 w-[1px] bg-outline-variant"></div>
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-error hover:bg-error-container/20 rounded-lg transition-colors" onClick={() => navigate('/')}>
            <span className="material-symbols-outlined text-sm">logout</span>
            退出登入
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 pt-20 px-gutter pb-xl overflow-y-auto">
        <div className="max-w-[1280px] mx-auto py-margin">
          
          {/* Class Selection Row */}
          <section className="mb-margin">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-h3 text-xl text-on-surface">班级选择</h3>
              <span className="text-sm text-outline">当前：{activeClass}班</span>
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
                      <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: '"FILL" 1' }}>check_circle</span>
                    )}
                  </div>
                  <p className="font-h3 text-lg text-on-surface mb-1">{cls.topic}</p>
                  <p className="text-sm text-outline">{cls.students} 名学生</p>
                </button>
              ))}
            </div>
          </section>

          {/* Student Monitoring Table */}
          <section className="mb-margin">
            <div className="bg-white rounded-xl border border-outline-variant shadow-sm overflow-hidden">
              <div className="px-md py-4 border-b border-outline-variant flex justify-between items-center bg-surface-container-lowest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">monitoring</span>
                  <h3 className="font-h3 text-xl text-on-surface">{activeClass}班 学生实时监控</h3>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center bg-surface-container-low rounded-lg px-3 py-1.5 border border-outline-variant">
                    <span className="material-symbols-outlined text-outline text-sm mr-2">search</span>
                    <input className="bg-transparent border-none focus:ring-0 text-sm w-32 outline-none" placeholder="搜索学生..." type="text" />
                  </div>
                  <button className="p-2 rounded-lg hover:bg-surface-container transition-colors">
                    <span className="material-symbols-outlined text-outline">refresh</span>
                  </button>
                </div>
              </div>
              
              <div className="overflow-x-auto">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-gutter gap-y-4 p-md">
                  {loading ? (
                    <div className="col-span-1 lg:col-span-2 py-8 flex justify-center"><span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span></div>
                  ) : (
                    students.map(student => (
                      <div 
                        key={student.user_id}
                        onClick={() => navigate('/teacher/report', { state: { student_id: student.user_id, class_id: activeClass }})}
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
                      </div>
                    ))
                  )}
                  {!loading && students.length === 0 && (
                     <div className="col-span-1 lg:col-span-2 py-8 text-center text-outline">暂无学生数据</div>
                  )}
                </div>
              </div>

              {/* Pagination */}
              <div className="px-md py-4 bg-surface-container-low border-t border-outline-variant flex justify-between items-center">
                <span className="text-xs font-medium text-outline">当前显示 {activeClass}班 (42名学生中展示 14名)</span>
                <div className="flex gap-1">
                  <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">上一页</button>
                  <button className="px-3 py-1 bg-primary text-white border border-primary rounded-lg text-xs font-bold">1</button>
                  <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">2</button>
                  <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">下一页</button>
                </div>
              </div>
            </div>
          </section>

          {/* AI Insights Section */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
            <div className="md:col-span-2 bg-white rounded-xl border border-outline-variant shadow-sm p-md">
              <div className="flex items-center gap-2 mb-4">
                <span className="material-symbols-outlined text-primary">psychology</span>
                <h3 className="font-h3 text-xl text-on-surface">AI 洞察 (AI Insights)</h3>
              </div>
              <div className="space-y-4">
                <div className="p-4 bg-surface-container-low rounded-lg border-l-4 border-primary">
                  <p className="font-bold text-on-surface text-sm mb-1">本周课程状态概览</p>
                  <p className="text-sm text-on-surface-variant leading-relaxed">
                    {insights?.overview || '加载中...'}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 border border-outline-variant rounded-lg">
                    <p className="text-xs text-outline mb-2">平均活跃时间</p>
                    <p className="text-xl font-bold text-on-surface">{insights?.avg_duration || 0} <span className="text-xs text-outline font-normal">min/session</span></p>
                  </div>
                  <div className="p-3 border border-outline-variant rounded-lg">
                    <p className="text-xs text-outline mb-2">知识点覆盖率</p>
                    <p className="text-xl font-bold text-on-surface">{insights?.coverage_rate || 0}% <span className="text-xs text-green-500 font-normal">↑ 4%</span></p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
              <h4 className="font-bold text-on-surface text-sm mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-error text-lg">priority_high</span>
                需重点关注学生 (Special Students)
              </h4>
              <div className="space-y-3">
                {insights?.special_students?.map(ss => (
                  <div 
                    key={ss.user_id}
                    onClick={() => navigate('/teacher/report', { state: { student_id: ss.user_id, class_id: activeClass }})}
                    className={`flex items-center justify-between p-2 rounded-lg transition-colors cursor-pointer border border-transparent ${ss.border_color}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${ss.avatar_color}`}>{ss.avatar_text}</div>
                      <div>
                        <p className="text-xs font-bold">{ss.username} ({ss.english_name})</p>
                        <p className={`text-[10px] ${ss.avatar_color.split(' ')[1]}`}>{ss.issue}</p>
                      </div>
                    </div>
                    <span className="material-symbols-outlined text-outline text-sm">chevron_right</span>
                  </div>
                ))}
                {!insights?.special_students?.length && !loading && (
                   <p className="text-xs text-outline text-center py-4">暂无需要特殊关注的学生</p>
                )}
              </div>
              <button className="w-full mt-6 py-2 border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">生成完整班级报表</button>
            </div>
          </section>

        </div>
      </main>
    </div>
  );
}
