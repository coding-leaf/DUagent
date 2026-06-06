import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { teachingService } from '../api/services/teaching';
import FeedbackStatus from '../components/FeedbackStatus';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';

export default function TeacherStudentReport() {
  const navigate = useNavigate();
  const location = useLocation();

  const queryParams = new URLSearchParams(location.search);
  const classId = queryParams.get('course_id');
  const studentId = queryParams.get('student_id');

  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(!!classId && !!studentId);

  useEffect(() => {
    if (!classId || !studentId) {
      return;
    }
    teachingService.getStudentReport(classId, studentId).then(res => {
      if (res.code === 200) {
        setReport(res.data);
      }
    }).catch(console.error).finally(() => setLoading(false));
  }, [classId, studentId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="loading" title="加载报告数据..." />
      </div>
    );
  }

  if (!classId || !studentId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="error" title="参数缺失" description="请从学生列表页面进入" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="error" title="未找到报告数据" description="请检查课程和学生信息是否正确" />
      </div>
    );
  }

  return (
    <div className="text-on-surface bg-background font-body-md antialiased selection:bg-primary-container selection:text-on-primary-container flex flex-col min-h-screen">
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
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-error hover:bg-error-container/20 rounded-lg transition-colors cursor-pointer" onClick={() => navigate('/')}>
            <span className="material-symbols-outlined text-sm">logout</span>
            退出登入
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 pt-20 px-gutter pb-xl overflow-y-auto">
        <div className="max-w-[1280px] mx-auto py-margin">
          
          {/* Breadcrumb & Header */}
          <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-slate-400 text-sm mb-1 cursor-pointer hover:text-primary transition-colors" onClick={() => navigate('/teacher')}>
                <span className="material-symbols-outlined text-xs transform rotate-180">chevron_right</span>
                <span>返回学生列表</span>
              </div>
              <h1 className="font-h1 text-h1 text-on-background">学情详尽报告 <span className="text-primary-container">· {report.student?.real_name || report.student?.student_id || '学生报告'}</span></h1>
            </div>
            <div className="flex gap-3">
              <button disabled className="flex items-center px-4 py-2 bg-slate-100 border border-outline-variant rounded-xl font-label-sm text-label-sm text-slate-400 cursor-not-allowed opacity-60">
                <span className="material-symbols-outlined mr-2">print</span> 导出报告 (暂不可用)
              </button>
              <button disabled className="flex items-center px-4 py-2 bg-slate-200 text-slate-400 rounded-xl font-label-sm text-label-sm font-bold cursor-not-allowed opacity-60">
                <span className="material-symbols-outlined mr-2">send</span> 发送反馈 (暂不可用)
              </button>
            </div>
          </div>

          {/* TOP SECTION: Profile and Analysis */}
          {useMock && (
            <>
              <section className="mb-8">
            {/* Profile Card */}
            <div className="relative overflow-hidden bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-8 hover:-translate-y-0.5 transition-transform duration-300">
              <div className="absolute top-0 right-0 w-64 h-64 -mr-20 -mt-20 opacity-10">
                <img alt="Abstract AI" className="w-full h-full object-cover rounded-full" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCzMAEOheT0KjN_V4Fs50iduiqAbY41brWEWJxp4OTj7_UEp-xIaxcjCg_nD7gFlxpJA02J20-08588bHb0rXh9DPDwVliY11SE63OLe49p49EPdhdtV3tTmvxzYZDpegvuIRbUOt73p55PYcIPkbbpQ2m9zU1qHjuedH2kiKkGvLzCoqlaAVBdvhbk1k_bRiNJkR1nKy0pWxkiz8th0-NwNlCiS_m3BF-O5D1TV2PGqwwetrQvRYYY_qJql5n3DmySA98y7i-zv3sV" />
              </div>
              <div className="relative">
                <div className="relative w-32 h-32 rounded-full border-4 border-slate-100 overflow-hidden bg-slate-100">
                  <img alt="李华 Avatar" className="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuC07BOGJWseHN9894enM_L7lbL1vknF4bHPCaAyGzyUrT7QT9ojTqzKZd17pkUqgZxu_g1e-UUG6gk1UC_Z2aa-joN2oOlX8fqOWDwrDXOE4pUdrNbJ0EZGcKTA6lMEXTrjLnY2_q-kHPKiUSvs0oO2CTPzmQFrLJ_p4JMk9FPtJ-BgXnCfTEvyFHg7LihxKWSWyiW9jwSnp2xGWINNyUWGusGrFi9r4sy9ch386vd528d4f-kqTB4wQNzXiauJm_zQapOmDKlx49pt" />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-4 mb-2">
                  <h1 className="font-h1 text-3xl text-on-surface">{report.username}</h1>
                  <span className="bg-primary text-white text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">学生</span>
                </div>
                <p className="text-body-md text-secondary font-body-md mb-2">学号: {report.student_id} · {report.major}</p>
                <div className="flex gap-2">
                  <span className="px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-bold">在读</span>
                </div>
                
                <div className="pt-6 mt-4 border-t border-slate-100">
                  <div>
                    <p className="text-2xl font-black text-slate-900">—</p>
                    <p className="text-[10px] text-slate-400 uppercase tracking-tighter">综合评分</p>
                  </div>
                </div>
              </div>
            </div>

          </section>

          {/* Bento Grid Top Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-6 mb-12">
            
            {/* Modality Card */}
            <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)] flex flex-col items-center hover:-translate-y-0.5 transition-transform duration-300">
              <div className="w-full flex justify-between items-center mb-6">
                <h3 className="font-h3 text-xl flex items-center gap-2 text-on-surface font-bold">
                  <span className="material-symbols-outlined text-cyan-500">pie_chart</span> 模态偏好
                </h3>
              </div>
              <div className="relative w-52 h-52 flex items-center justify-center p-2">
                <p className="text-sm text-slate-400 text-center">模态偏好数据待 Backend 返回</p>
              </div>
              <p className="text-xs text-slate-500 mt-4 leading-relaxed w-full text-left">
                <span className="font-bold text-primary">AI诊断：</span> {report.ai_diagnosis}
              </p>
            </div>

            {/* Granularity Card */}
            <div className="lg:col-span-8 bg-white p-8 rounded-2xl border border-gray-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)] flex flex-col hover:-translate-y-0.5 transition-transform duration-300">
              <div className="mb-8">
                <h3 className="font-h3 text-xl mb-4 flex items-center gap-2 text-on-surface font-bold">
                  <span className="material-symbols-outlined text-cyan-500">tune</span> 引导粒度
                </h3>
                <p className="text-body-md text-secondary">根据当前任务难度与心流状态，动态调整智能体的介入深度。</p>
              </div>
              <div className="relative px-6 py-12 flex-1">
                <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden relative">
                  <div className="h-full bg-gradient-to-r from-cyan-400 to-cyan-600" style={{ width: '50%' }}></div>
                </div>
                <div className="flex justify-between items-center absolute w-full left-0 top-0 mt-[38px] px-4">
                  <div className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-white border-4 border-slate-200 shadow-sm z-10"></div>
                    <div className="mt-6 text-center">
                      <p className="text-label-sm font-bold text-slate-400">L1: 启发点拨</p>
                      <p className="text-[10px] text-slate-400 mt-1">核心思路提示</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-10 h-10 rounded-full bg-cyan-500 border-[6px] border-white shadow-xl shadow-cyan-200 z-20"></div>
                    <div className="mt-4 text-center">
                      <p className="text-label-sm font-bold text-cyan-600">L2: 伴学拆解</p>
                      <p className="text-[10px] text-cyan-400 mt-1">分步引导学习</p>
                    </div>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-white border-4 border-slate-200 shadow-sm z-10"></div>
                    <div className="mt-6 text-center">
                      <p className="text-label-sm font-bold text-slate-400">L3: 保姆生成</p>
                      <p className="text-[10px] text-slate-400 mt-1">全自动代码生成</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-8 bg-cyan-50 p-5 rounded-xl flex items-start gap-4 border border-cyan-100">
                <span className="material-symbols-outlined text-cyan-600 mt-0.5">verified</span>
                <p className="text-sm text-cyan-700 leading-relaxed">
                  <span className="font-bold">系统建议：</span>{report.guidance_suggestion}
                </p>
              </div>
            </div>

            {/* Knowledge Map */}
            <div className="lg:col-span-7 bg-white p-8 rounded-2xl border border-gray-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)] relative overflow-hidden hover:-translate-y-0.5 transition-transform duration-300">
              <div className="absolute top-0 right-0 p-4 opacity-5">
                <span className="material-symbols-outlined text-9xl">hub</span>
              </div>
              <h3 className="font-h3 text-xl mb-8 flex items-center gap-2 text-on-surface font-bold">
                <span className="material-symbols-outlined text-cyan-500">grid_view</span> 知识坐标 &amp; 认知盲区
              </h3>
              <div className="flex flex-wrap gap-4 relative">
                {report.knowledge_coordinates?.map((kc, i) => {
                  let style;
                  let icon;
                  if (kc.type === 'mastered') {
                    style = 'bg-green-50 text-green-700 border-green-100';
                    icon = 'check_circle';
                  } else if (kc.type === 'learning') {
                    style = 'bg-blue-50 text-blue-700 border-blue-100';
                    icon = 'check_circle';
                  } else {
                    style = 'bg-orange-50 text-orange-700 border-orange-200 shadow-md shadow-orange-100';
                    icon = 'local_fire_department';
                  }
                  return (
                    <span key={i} className={`px-5 py-3 rounded-xl border font-bold flex items-center gap-2 text-sm transition-all hover:scale-105 ${style}`}>
                      <span className="material-symbols-outlined text-base" style={kc.type === 'weak' ? { fontVariationSettings: '"FILL" 1' } : {}}>{icon}</span> {kc.name}
                    </span>
                  );
                })}
              </div>
            </div>

            {/* Learning Heat and Accuracy Card */}
            <div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-[0px_4px_20px_rgba(0,0,0,0.04)] flex flex-col hover:-translate-y-0.5 transition-transform duration-300">
              <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface font-bold">
                <span className="material-symbols-outlined text-cyan-500">analytics</span> 学习热度与准度
              </h3>
              <div className="flex-1 flex flex-col space-y-4">
                <div className="h-32 w-full relative flex items-end justify-between px-2">
                  <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 100">
                    <path d="M0,60 Q10,50 20,40 T40,45 T60,30 T80,35 T100,20" fill="none" stroke="#00677f" strokeWidth="2"></path>
                    <path d="M0,80 Q10,75 20,60 T40,65 T60,55 T80,45 T100,40" fill="none" stroke="#00d1ff" strokeDasharray="2 1" strokeWidth="2"></path>
                  </svg>
                  <div className="absolute bottom-0 w-full flex justify-between text-[8px] text-slate-400 font-bold px-1">
                    <span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span><span>周六</span><span>周日</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-2">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-1 bg-cyan-400"></div>
                    <span className="text-xs text-secondary font-bold">近期学习频度</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-1 bg-primary"></div>
                    <span className="text-xs text-secondary font-bold">做题准确率</span>
                  </div>
                </div>
                <div className="pt-4 border-t border-slate-50">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex flex-col items-center text-center">
                    <span className="text-primary font-black text-lg">待统计</span>
                    <p className="text-[10px] text-slate-400 uppercase font-bold">本周最高准度</p>
                  </div>
                </div>
              </div>
            </div>

          </div>

          {/* Divider with Label */}
          <div className="relative flex items-center py-4 mb-8">
            <div className="flex-grow border-t border-slate-200"></div>
            <span className="flex-shrink mx-4 text-slate-400 font-bold text-xs uppercase tracking-[0.2em]">Learning Outcomes &amp; AI Analysis</span>
            <div className="flex-grow border-t border-slate-200"></div>
          </div>

          {/* BOTTOM SECTION: Learning Results */}
          <div className="grid grid-cols-12 gap-gutter pb-12">
            
            {/* AI Insight Card */}
            <div className="col-span-12 lg:col-span-8 glass-panel rounded-xl p-md flex flex-col md:flex-row gap-md items-start shadow-[0px_4px_20px_rgba(0,0,0,0.04)] hover:-translate-y-0.5 transition-transform duration-300">
              <div className="flex-shrink-0 w-16 h-16 bg-primary-container/20 rounded-full flex items-center justify-center">
                <span className="material-symbols-outlined text-primary text-3xl" style={{ fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
              </div>
              <div>
                <h3 className="font-h3 text-h3 mb-2 flex items-center">
                  AI 智能分析报告
                  <span className="ml-3 px-2 py-0.5 bg-cyan-100 text-cyan-700 text-[10px] rounded-full font-bold">实时分析</span>
                </h3>
                <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">
                  {report.ai_insight}
                </p>
                <div className="p-4 mt-4 bg-slate-50 rounded-lg border-l-4 border-primary-container">
                  <h4 className="text-xs font-bold text-primary uppercase mb-2">下一阶段行动建议</h4>
                  <ul className="text-sm text-slate-700 space-y-2 list-disc pl-4">
                    {report.action_suggestions?.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Exercise/Test Mastery Chart */}
            <div className="col-span-12 lg:col-span-4 glass-panel rounded-xl p-md shadow-[0px_4px_20px_rgba(0,0,0,0.04)] hover:-translate-y-0.5 transition-transform duration-300">
              <h3 className="font-h3 text-h3 mb-sm flex items-center">
                <span className="material-symbols-outlined mr-2 text-primary">assessment</span> 练习掌握度
              </h3>
              <div className="flex flex-col gap-4 mt-6">
                {report.mastery_stats?.map((stat, i) => (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-between text-label-sm font-label-sm">
                      <span>{stat.name}</span>
                      <span className="text-primary">{stat.percent}%</span>
                    </div>
                    <div className="h-2 bg-surface-container rounded-full overflow-hidden">
                      <div className="h-full bg-primary-container" style={{ width: `${stat.percent}%` }}></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Path Progression Table */}
            <div className="col-span-12 lg:col-span-7 glass-panel rounded-xl p-md shadow-[0px_4px_20px_rgba(0,0,0,0.04)] hover:-translate-y-0.5 transition-transform duration-300">
              <h3 className="font-h3 text-h3 mb-md">学习路径进度</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="pb-3 font-label-sm text-label-sm text-outline">模块名称</th>
                      <th className="pb-3 font-label-sm text-label-sm text-outline">当前状态</th>
                      <th className="pb-3 font-label-sm text-label-sm text-outline">平均耗时</th>
                      <th className="pb-3 font-label-sm text-label-sm text-outline">达成率</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {report.learning_path_progress?.map((path, i) => {
                      let statusStyle;
                      let textStyle;
                      if (path.status === '已过关') {
                        statusStyle = 'bg-green-50 text-green-600';
                        textStyle = 'text-green-600';
                      } else if (path.status === '进行中') {
                        statusStyle = 'bg-cyan-50 text-cyan-600';
                        textStyle = 'text-primary';
                      } else {
                        statusStyle = 'bg-gray-100 text-gray-500';
                        textStyle = 'text-outline';
                      }
                      
                      return (
                        <tr key={i} className="group hover:bg-surface-container-low transition-colors">
                          <td className="py-4 font-body-md text-body-md">{path.module}</td>
                          <td className="py-4">
                            <span className={`px-3 py-1 rounded-full text-xs font-bold ${statusStyle}`}>{path.status}</span>
                          </td>
                          <td className="py-4 font-body-md text-body-md text-on-surface-variant">{path.time}</td>
                          <td className={`py-4 font-bold ${textStyle}`}>{path.completion}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </>
      )}

      {!useMock && (
        <div className="space-y-8">
          {/* Profile banner */}
          <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm flex flex-col md:flex-row items-center gap-6">
            <div className="w-20 h-20 rounded-full overflow-hidden bg-slate-100 flex-shrink-0">
              <img alt="Avatar" className="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuC07BOGJWseHN9894enM_L7lbL1vknF4bHPCaAyGzyUrT7QT9ojTqzKZd17pkUqgZxu_g1e-UUG6gk1UC_Z2aa-joN2oOlX8fqOWDwrDXOE4pUdrNbJ0EZGcKTA6lMEXTrjLnY2_q-kHPKiUSvs0oO2CTPzmQFrLJ_p4JMk9FPtJ-BgXnCfTEvyFHg7LihxKWSWyiW9jwSnp2xGWINNyUWGusGrFi9r4sy9ch386vd528d4f-kqTB4wQNzXiauJm_zQapOmDKlx49pt" />
            </div>
            <div className="flex-grow text-center md:text-left">
              <h2 className="text-2xl font-bold text-on-surface mb-1">{report.student?.real_name || report.student?.student_id || '学生'}</h2>
              <p className="text-sm text-secondary">学号: {report.student?.student_id || '未知'} · 班级ID: {classId}</p>
            </div>
            <div className="bg-primary/5 border border-primary/20 rounded-xl px-6 py-4 flex flex-col items-center">
              <span className="text-3xl font-black text-primary">{report.evaluation_summary?.overall_score || 0}</span>
              <span className="text-[10px] text-secondary font-bold uppercase tracking-wider">综合评分</span>
            </div>
          </div>

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Quiz Stats */}
            <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
                <span className="material-symbols-outlined text-primary text-xl">assessment</span>
                在线测试统计 (Quiz Stats)
              </h3>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-surface-container rounded p-3 text-center">
                  <span className="text-xl font-bold text-on-surface block">{report.quiz_stats?.total_attempts || 0}</span>
                  <span className="text-[10px] text-secondary">总测试</span>
                </div>
                <div className="bg-surface-container rounded p-3 text-center">
                  <span className="text-xl font-bold text-on-surface block">{report.quiz_stats?.avg_score || 0}%</span>
                  <span className="text-[10px] text-secondary">平均分</span>
                </div>
                <div className="bg-surface-container rounded p-3 text-center">
                  <span className="text-xl font-bold text-on-surface block">{Math.round((report.quiz_stats?.avg_time_spent || 0) / 60)}m</span>
                  <span className="text-[10px] text-secondary">均时</span>
                </div>
              </div>
            </div>

            {/* Path Progress */}
            <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
                <span className="material-symbols-outlined text-primary text-xl">account_tree</span>
                学习路径进度 (Path Progress)
              </h3>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-secondary mb-1">当前学习节点</p>
                  <p className="text-base font-bold text-on-surface truncate max-w-[120px]">{report.path_progress?.current_node || '暂无活跃节点'}</p>
                </div>
                <div className="flex flex-col items-end">
                  <span className="text-xl font-black text-primary">
                    {report.path_progress?.completed_nodes || 0} / {report.path_progress?.total_nodes || 0}
                  </span>
                  <span className="text-[10px] text-secondary">已完成节点</span>
                </div>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-primary h-full transition-all duration-300"
                  style={{ width: `${((report.path_progress?.completed_nodes || 0) / (report.path_progress?.total_nodes || 1)) * 100}%` }}
                ></div>
              </div>
            </div>

            {/* Modality Preference */}
            <div className="bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
                <span className="material-symbols-outlined text-primary text-xl">psychology</span>
                模态偏好 (Modal Preference)
              </h3>
              <div className="flex flex-wrap gap-2">
                {report.profile_summary?.modal_preference && report.profile_summary.modal_preference.length > 0 ? (
                  report.profile_summary.modal_preference.map((p, idx) => (
                    <span key={idx} className="px-3 py-1.5 bg-cyan-50 text-cyan-700 text-xs font-bold rounded-lg border border-cyan-100 flex items-center gap-1">
                      <span className="text-[10px] opacity-60">#{idx + 1}</span> {p}
                    </span>
                  ))
                ) : (
                  <p className="text-xs text-outline italic text-center py-4">暂无偏好数据</p>
                )}
              </div>
            </div>
          </div>

          {/* Details Section */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            {/* Left Column: Weak Points & Mastered count */}
            <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-6 flex flex-col justify-between">
              <div>
                <h3 className="text-base font-bold text-on-surface mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-orange-500">local_fire_department</span>
                  薄弱知识点 (Weak Points)
                </h3>
                <div className="flex flex-wrap gap-2 mt-3">
                  {report.weak_points?.length > 0 ? (
                    report.weak_points.map((wp, i) => (
                      <div key={i} className="px-3 py-2 bg-orange-50 rounded-lg border border-orange-100 text-xs">
                        <span className="font-bold text-orange-700">{wp.knowledge_point}</span>
                        <span className="text-orange-500 ml-2">
                          {wp.error_count}/{wp.total_attempts} 错 ({Math.round(wp.error_rate * 100)}%)
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-outline italic">暂无薄弱点</p>
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-50 grid grid-cols-2 gap-4">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
                  <span className="text-xl font-bold text-green-600 block">{report.profile_summary?.knowledge_mastered || 0}</span>
                  <span className="text-[10px] text-secondary">已掌握知识点</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
                  <span className="text-xl font-bold text-orange-600 block">{report.profile_summary?.knowledge_weak || 0}</span>
                  <span className="text-[10px] text-secondary">薄弱知识点数</span>
                </div>
              </div>
            </div>

            {/* Right Column: Recent Activity */}
            <div className="md:col-span-6 bg-white p-6 rounded-2xl border border-outline-variant shadow-sm space-y-4">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2 border-b border-slate-50 pb-3">
                <span className="material-symbols-outlined text-primary text-xl">timeline</span>
                最近学习活动 (Recent Activity)
              </h3>
              <div className="space-y-4 max-h-[220px] overflow-y-auto pr-2 scrollbar-thin">
                {report.recent_activity?.length > 0 ? (
                  report.recent_activity.map((ra, i) => (
                    <div key={i} className="flex items-center gap-3 pb-3 border-b border-slate-50 last:border-0">
                      <div className="w-8 h-8 rounded-full bg-cyan-100 flex items-center justify-center flex-shrink-0">
                        <span className="material-symbols-outlined text-cyan-600 text-sm">exercise</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-on-surface truncate">{ra.chapter || '练习'}</p>
                        <p className="text-[10px] text-outline">
                          {ra.created_at ? new Date(ra.created_at).toLocaleDateString('zh-CN') : ''}
                        </p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <span className="text-sm font-bold text-primary">{Math.round(ra.score)}%</span>
                        <p className="text-[10px] text-outline">{ra.correct_count}/{ra.total_count} 正确</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-outline italic text-center py-8">暂无近期活动</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
        </div>
      </main>
    </div>
  );
}
