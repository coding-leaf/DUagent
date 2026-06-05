import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { profileService } from '../api/services/profile';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';

export default function StudentProfile() {
  const navigate = useNavigate();
  const { activeCourseId } = useCourse();
  const [profileData, setProfileData] = useState(null);
  const [effectsData, setEffectsData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      if (!activeCourseId) return;
      try {
        setLoading(true);
        const [profileRes, effectsRes] = await Promise.all([
          profileService.getStudentProfile(activeCourseId),
          profileService.getLearningEffects(activeCourseId)
        ]);
        if (profileRes.code === 200) setProfileData(profileRes.data);
        if (effectsRes.code === 200) setEffectsData(effectsRes.data);
      } catch (error) {
        console.error("Failed to fetch profile data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [activeCourseId]);

  if (loading) {
    return (
      <div className="bg-background min-h-screen flex items-center justify-center">
        <span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span>
      </div>
    );
  }

  const { name, level, title, current_course, system_suggestion, avatar } = profileData || {};
  const { weekly_max_accuracy, total_duration_hours, knowledge_nodes } = effectsData || {};

  return (
    <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
      {/* TopNavBar */}
      <Navbar />

      {/* SideNavBar Component */}
      <Sidebar />

      {/* Main Content */}
      <main className="ml-0 lg:ml-64 pt-16">
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          {/* Profile Card */}
          <div className="relative overflow-hidden bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-8 mb-8">
            <div className="absolute top-0 right-0 w-64 h-64 -mr-20 -mt-20 opacity-10">
              <img alt="Abstract AI" className="w-full h-full object-cover rounded-full" src="https://lh3.googleusercontent.com/aida-public/AB6AXuCzMAEOheT0KjN_V4Fs50iduiqAbY41brWEWJxp4OTj7_UEp-xIaxcjCg_nD7gFlxpJA02J20-08588bHb0rXh9DPDwVliY11SE63OLe49p49EPdhdtV3tTmvxzYZDpegvuIRbUOt73p55PYcIPkbbpQ2m9zU1qHjuedH2kiKkGvLzCoqlaAVBdvhbk1k_bRiNJkR1nKy0pWxkiz8th0-NwNlCiS_m3BF-O5D1TV2PGqwwetrQvRYYY_qJql5n3DmySA98y7i-zv3sV" />
            </div>
            <div className="relative">
              <div className="relative w-32 h-32 rounded-full border-4 border-slate-100 overflow-hidden bg-slate-100">
                <img alt={name || "Elara Vance"} className="w-full h-full object-cover" src={avatar || "https://lh3.googleusercontent.com/aida-public/AB6AXuBTg47lCOZc44Rlbp-24EwwN1J7sw9qUGrEClZifNn2yEyMt3okEbKNeNk18UX3gnhRFnUqxiymGyo3rL5MABT0fuopo662xIbp65CFju53RoA6l2pZXVgSgjBxCPT4X4lU-o1LuDtdBELLv78_N-q2mEKlbxJRmmCL9Y2K4b9uTOGdt--9KeTRfuTkr6rxCoUCoNPgytsazeMrZQJrccuvaETuIbMLP5YXtAHczyNNTuNHoL46_YW7s34lyn78eafbottYcLIRSeWv"} />
              </div>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-4 mb-2">
                <h1 className="font-h1 text-3xl text-on-surface">{name || "Elara Vance"}</h1>
                <span className="bg-primary-container text-on-primary-container text-xs px-4 py-1 rounded-full font-bold uppercase tracking-wider">Lvl {level || 14} {title || "Architect"}</span>
              </div>
              <p className="text-body-md text-secondary">当前进修课程：<span className="text-primary font-bold">{current_course || "数据结构与算法分析"}</span></p>
            </div>
          </div>

        {/* Bento Grid Main Content */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-6">
          {/* Modality Card */}
          <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center">
            <div className="w-full flex justify-between items-center mb-6">
              <h3 className="font-h3 text-xl flex items-center gap-2 text-on-surface">
                <span className="material-symbols-outlined text-cyan-500">pie_chart</span> 模态偏好
              </h3>
            </div>
            <div className="relative w-52 h-52 flex items-center justify-center p-2">
              <p className="text-sm text-secondary text-center">模态偏好数据待 Backend 返回</p>
            </div>
          </div>

          {/* Granularity Card */}
          <div className="lg:col-span-8 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm flex flex-col">
            <div className="mb-8">
              <h3 className="font-h3 text-xl mb-4 flex items-center gap-2 text-on-surface">
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
                <span className="font-bold">系统建议：</span>{system_suggestion || '检测到当前任务为“红黑树”，建议保持 L2 以确保认知留存，有助于理解平衡旋转逻辑。'}
              </p>
            </div>
          </div>

          {/* Knowledge Map */}
          <div className="lg:col-span-7 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-5">
              <span className="material-symbols-outlined text-9xl">hub</span>
            </div>
            <h3 className="font-h3 text-xl mb-8 flex items-center gap-2 text-on-surface">
              <span className="material-symbols-outlined text-cyan-500">grid_view</span> 知识坐标 &amp; 认知盲区
            </h3>
            <div className="flex flex-wrap gap-4 relative">
              {knowledge_nodes?.map((node, index) => {
                let colorClass = '';
                let icon = '';
                if (node.status === 'mastered') {
                  colorClass = 'bg-green-50 text-green-700 border-green-100';
                  icon = 'check_circle';
                } else if (node.status === 'familiar') {
                  colorClass = 'bg-blue-50 text-blue-700 border-blue-100';
                  icon = 'check_circle';
                } else if (node.status === 'weak') {
                  colorClass = 'bg-orange-50 text-orange-700 border-orange-200 shadow-orange-100';
                  icon = 'local_fire_department';
                } else if (node.status === 'blind_spot') {
                  colorClass = 'bg-red-50 text-red-700 border-red-200 shadow-red-100';
                  icon = 'local_fire_department';
                }
                
                return (
                  <span key={index} className={`px-5 py-3 rounded-xl border font-bold flex items-center gap-2 text-sm shadow-md transition-all hover:scale-105 ${colorClass}`}>
                    <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: '"FILL" 1' }}>{icon}</span> {node.name}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Learning Heat and Accuracy Card */}
          <div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm flex flex-col">
            <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
              <span className="material-symbols-outlined text-cyan-500">analytics</span> 学习热度与准度
            </h3>
            <div className="flex-1 flex flex-col space-y-4">
              <div className="h-32 w-full relative flex items-end justify-between px-2">
                {/* Simple SVG Line Chart for Frequency and Accuracy */}
                <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none" viewBox="0 0 100 100">
                  {/* Accuracy Line (Blue) */}
                  <path d="M0,60 Q10,50 20,40 T40,45 T60,30 T80,35 T100,20" fill="none" stroke="#00677f" strokeWidth="2"></path>
                  {/* Frequency Line (Cyan) */}
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
              <div className="pt-4 border-t border-slate-50 grid grid-cols-2 gap-4">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex flex-col items-center text-center">
                  <span className="text-primary font-black text-lg">{weekly_max_accuracy || 94}%</span>
                  <p className="text-[10px] text-slate-400 uppercase font-bold">本周最高准度</p>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex flex-col items-center text-center">
                  <span className="text-cyan-600 font-black text-lg">{total_duration_hours ? total_duration_hours + 'h' : '待统计'}</span>
                  <p className="text-[10px] text-slate-400 uppercase font-bold">累计学习时长</p>
                </div>
              </div>
            </div>
          </div>

          </div>
        </div>
      </main>

      {/* BottomNavBar (Mobile Only) */}
      <footer className="lg:hidden fixed bottom-0 w-full bg-white/80 backdrop-blur-md border-t border-gray-100 flex items-center justify-around h-16 z-50 px-4">
        <button onClick={() => navigate('/learning-path')} className="flex flex-col items-center gap-1 text-slate-400 cursor-pointer">
          <span className="material-symbols-outlined">account_tree</span>
          <span className="text-[10px] font-bold">学习</span>
        </button>
        <button onClick={() => navigate('/dashboard')} className="flex flex-col items-center gap-1 text-slate-400 cursor-pointer">
          <span className="material-symbols-outlined">library_books</span>
          <span className="text-[10px] font-bold">资源</span>
        </button>
        <div className="w-12 h-12 bg-cyan-600 rounded-full flex items-center justify-center text-white -mt-8 shadow-lg shadow-cyan-200">
          <span className="material-symbols-outlined">add</span>
        </div>
        <button onClick={() => navigate('/profile')} className="flex flex-col items-center gap-1 text-cyan-600 cursor-pointer">
          <span className="material-symbols-outlined">account_circle</span>
          <span className="text-[10px] font-bold">我的</span>
        </button>
      </footer>
    </div>
  );
}
