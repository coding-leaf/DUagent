import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { profileService } from '../api/services/profile';
import { useCourse } from '../context/CourseContext';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';

export default function StudentProfile() {
  const navigate = useNavigate();
  const { activeCourseId, courses } = useCourse();
const { user } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/purity -- relative time display needs current timestamp
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNow(Date.now());
  }, [profileData]);

  useEffect(() => {
    const fetchProfile = async () => {
      if (!activeCourseId) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const res = await profileService.getStudentProfile(activeCourseId);
        if (res.code === 200) setProfileData(res.data);
      } catch (error) {
        console.error("Failed to fetch profile data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [activeCourseId]);

  if (!activeCourseId) {
    return (
      <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
        <Navbar />
        <Sidebar />
        <main className="ml-0 lg:ml-64 pt-16">
          <div className="max-w-[1280px] mx-auto px-6 py-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
            <span className="material-symbols-outlined text-6xl text-slate-300 mb-6">person_search</span>
            <h2 className="font-h1 text-2xl text-on-surface mb-3">还没有可查看的课程画像</h2>
            <p className="text-body-md text-secondary max-w-md mb-8">
              加入一门课程后，这里会展示你的模态偏好、引导粒度、知识坐标和学习状态。
            </p>
            <button
              onClick={() => navigate('/dashboard')}
              className="px-6 py-2.5 bg-cyan-600 text-white rounded-xl font-bold hover:bg-cyan-700 transition-colors cursor-pointer"
            >
              去课程页
            </button>
          </div>
        </main>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-background min-h-screen flex items-center justify-center">
        <span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span>
      </div>
    );
  }

  const profile = profileData || {};
  const {
    modal_preference = {},
    guidance_level = { current: 'L2', updated_at: '' },
    knowledge_coordinates = [],
    cognitive_blindspots = [],
    drive_intent = { type: 'casual', intensity: 30 },
    discipline_badge = { subject: '', level: '', streak_days: 0 },
  } = profile;

  // 姓名优先级：real_name → username → 兜底
  const displayName = user?.real_name || user?.username || '学生';
  const displayInitial = (user?.real_name || user?.username || '学').charAt(0);

  // 当前课程名：从 CourseContext 按 activeCourseId 查找
  const currentCourseName = courses.find(c => c.id === activeCourseId)?.name || '未选择';

  // 相对时间格式化
  const daysAgoText = (iso, suffix) => {
    if (!iso) return null;
    const diff = now - new Date(iso).getTime();
    const days = Math.floor(diff / 86400000);
    return days === 0 ? `今天${suffix}` : `${days} 天前${suffix}`;
  };

  const guidanceUpdatedText = guidance_level.updated_at
    ? daysAgoText(guidance_level.updated_at, '')
    : null;

  return (
    <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
      {/* TopNavBar */}
      <Navbar />

      {/* SideNavBar Component */}
      <Sidebar />

      {/* Main Content */}
      <main className="ml-0 lg:ml-64 pt-16">
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          {/* 卡片 1：个人信息 */}
          <div className="relative overflow-hidden bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-8 mb-8">
            <div className="absolute top-0 right-0 w-64 h-64 -mr-20 -mt-20 opacity-5">
              <span className="material-symbols-outlined text-9xl">school</span>
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
                {discipline_badge.level && discipline_badge.subject ? (
                  <span className="bg-amber-50 text-amber-700 text-xs px-4 py-1 rounded-full font-bold uppercase tracking-wider border border-amber-200">
                    学科勋章：{discipline_badge.subject} · {discipline_badge.level}
                  </span>
                ) : (
                  <span className="bg-slate-100 text-slate-400 text-xs px-4 py-1 rounded-full">学科勋章：—</span>
                )}
              </div>
              <p className="text-body-md text-secondary">当前进修课程：<span className="text-primary font-bold">{currentCourseName}</span></p>
            </div>
          </div>

        {/* Bento Grid Main Content */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-6">
          {/* 卡片 2：模态偏好 */}
          <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
              <span className="material-symbols-outlined text-cyan-500">pie_chart</span> 模态偏好
            </h3>
            <div className="flex flex-col gap-4">
              {[
                { key: 'video_animation', label: '视频动画' },
                { key: 'chart_logic', label: '图表逻辑' },
                { key: 'text_analysis', label: '文本分析' },
                { key: 'code_practice', label: '代码实操' },
                { key: 'formula_derivation', label: '公式推导' },
              ].map(({ key, label }) => {
                const value = modal_preference[key] ?? 0;
                const colorClass = value >= 70 ? 'bg-cyan-600' : value >= 40 ? 'bg-cyan-400' : 'bg-slate-300';
                return (
                  <div key={key}>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs text-secondary font-bold">{label}</span>
                      <span className="text-xs text-cyan-700 font-bold">{value}%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full ${colorClass} rounded-full transition-all`} style={{ width: `${value}%` }}></div>
                    </div>
                  </div>
                );
              })}
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
                <div className="h-full bg-gradient-to-r from-cyan-400 to-cyan-600" style={{ width: `${
                  guidance_level.current === 'L1' ? '33%' :
                  guidance_level.current === 'L3' ? '100%' : '66%'
                }` }}></div>
              </div>
              <div className="flex justify-between items-center absolute w-full left-0 top-0 mt-[38px] px-4">
                <div className="flex flex-col items-center">
                  <div className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 ${
                    guidance_level.current === 'L1'
                      ? 'bg-cyan-500 border-white shadow-cyan-200'
                      : 'bg-white border-slate-200'
                  }`}></div>
                  <div className="mt-6 text-center">
                    <p className={`text-label-sm font-bold ${guidance_level.current === 'L1' ? 'text-cyan-600' : 'text-slate-400'}`}>L1: 启发点拨</p>
                    <p className="text-[10px] text-slate-400 mt-1">核心思路提示</p>
                  </div>
                </div>
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 rounded-full border-[6px] shadow-xl z-20 ${
                    guidance_level.current === 'L2'
                      ? 'bg-cyan-500 border-white shadow-cyan-200'
                      : 'bg-white border-slate-200 shadow-sm'
                  }`}></div>
                  <div className="mt-4 text-center">
                    <p className={`text-label-sm font-bold ${guidance_level.current === 'L2' ? 'text-cyan-600' : 'text-slate-400'}`}>L2: 伴学拆解</p>
                    <p className={`text-[10px] ${guidance_level.current === 'L2' ? 'text-cyan-400' : 'text-slate-400'} mt-1`}>分步引导学习</p>
                  </div>
                </div>
                <div className="flex flex-col items-center">
                  <div className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 ${
                    guidance_level.current === 'L3'
                      ? 'bg-cyan-500 border-white shadow-cyan-200'
                      : 'bg-white border-slate-200'
                  }`}></div>
                  <div className="mt-6 text-center">
                    <p className={`text-label-sm font-bold ${guidance_level.current === 'L3' ? 'text-cyan-600' : 'text-slate-400'}`}>L3: 保姆生成</p>
                    <p className="text-[10px] text-slate-400 mt-1">全自动代码生成</p>
                  </div>
                </div>
              </div>
            </div>
            {guidanceUpdatedText && (
              <p className="text-xs text-slate-400 mt-4 text-center">
                更新于 {guidanceUpdatedText}
              </p>
            )}
          </div>

          {/* 卡片 4：知识坐标 + 认知盲区 */}
          <div className="lg:col-span-7 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
            <h3 className="font-h3 text-xl mb-8 flex items-center gap-2 text-on-surface">
              <span className="material-symbols-outlined text-cyan-500">grid_view</span> 知识坐标 &amp; 认知盲区
            </h3>

            {/* 上半：知识坐标 */}
            <div className="mb-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">知识坐标</p>
              {knowledge_coordinates.length > 0 ? (
                <div className="flex flex-wrap gap-3">
                  {knowledge_coordinates.map((node, i) => {
                    const isMastered = node.status === 'mastered';
                    return (
                      <span
                        key={i}
                        className={`px-4 py-2 rounded-lg border text-sm font-bold flex items-center gap-2 transition-all hover:scale-105 ${
                          isMastered
                            ? 'bg-green-50 text-green-700 border-green-100'
                            : 'bg-amber-50 text-amber-700 border-amber-100'
                        }`}
                      >
                        <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: '"FILL" 1' }}>
                          {isMastered ? 'check_circle' : 'sync'}
                        </span>
                        {node.name}
                        {isMastered && node.mastered_at && (
                          <span className="text-green-400 text-xs font-normal ml-1">
                            · {daysAgoText(node.mastered_at, '掌握')}
                          </span>
                        )}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-slate-400 py-8 text-center">暂无知识坐标数据</p>
              )}
            </div>

            {/* 下半：认知盲区 */}
            <div className="border-t border-slate-100 pt-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">认知盲区</p>
              {cognitive_blindspots.length > 0 ? (
                <div className="space-y-2">
                  {cognitive_blindspots.map((item, i) => {
                    const severityColors = {
                      high: 'bg-red-50 text-red-700 border-red-100',
                      medium: 'bg-amber-50 text-amber-700 border-amber-100',
                      low: 'bg-slate-100 text-slate-500 border-slate-200',
                    };
                    const severityLabels = { high: '高', medium: '中', low: '低' };
                    const colorClass = severityColors[item.severity] || severityColors.low;
                    const label = severityLabels[item.severity] || item.severity;
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${colorClass} border`}>
                          {label}
                        </span>
                        <span className="text-sm text-on-surface">{item.name}</span>
                        <span className="text-xs text-slate-400">· 错误 {item.error_count} 次</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-slate-400 py-4 text-center">暂无认知盲区记录</p>
              )}
            </div>
          </div>

          {/* 卡片 5：驱动力 + 学科勋章 */}
          <div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
            <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
              <span className="material-symbols-outlined text-cyan-500">psychology</span> 学习状态
            </h3>

            {/* 驱动力 */}
            <div className="mb-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">驱动力</p>
              <div className="flex items-center gap-4">
                <span className="px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg text-sm font-bold border border-cyan-100">
                  {{
                    exam_sprint: '备考冲刺',
                    daily_homework: '日常作业',
                    casual: '兴趣驱动',
                  }[drive_intent.type] || drive_intent.type}
                </span>
                <div className="flex-1">
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${drive_intent.intensity}%` }}></div>
                  </div>
                </div>
                <span className="text-xs text-slate-500 font-bold w-8 text-right">{drive_intent.intensity}%</span>
              </div>
            </div>

            {/* 学科勋章 */}
            <div className="border-t border-slate-100 pt-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">学科勋章</p>
              {discipline_badge.subject && discipline_badge.level ? (
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center border-4 border-amber-200">
                    <span className="material-symbols-outlined text-2xl text-amber-600" style={{ fontVariationSettings: '"FILL" 1' }}>
                      verified
                    </span>
                  </div>
                  <div>
                    <p className="font-bold text-on-surface">
                      学科勋章：{discipline_badge.subject} · {discipline_badge.level}
                    </p>
                    <p className="text-sm text-slate-500 mt-1">
                      连续打卡 <span className="text-amber-600 font-bold">{discipline_badge.streak_days}</span> 天
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-400 py-4 text-center">暂无学科勋章</p>
              )}
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
