import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { profileService } from '../api/services/profile';
import { authService } from '../api/services/auth';
import { taskService } from '../api/services/task';
import { useCourse } from '../context/CourseContext';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';

const PROFILE_VALUE_LABELS = {
  exam_sprint: '备考冲刺',
  daily_homework: '课后巩固',
  casual: '兴趣拓展',
  video_animation: '视频动画',
  chart_logic: '图表逻辑',
  text_analysis: '文本解析',
  code_practice: '代码实操',
  formula_derivation: '公式推导',
  L1: '启发点拨',
  L2: '分步伴学',
  L3: '详细讲解',
  starter: '入门起步',
  active: '稳定学习',
  focused: '高频投入',
};

const PROFILE_DIMENSION_LABELS = {
  learning_goal: '当前学习方向',
  weak_points: '待提升内容',
  resource_preference: '学习资料偏好',
  guidance_level: '辅导方式',
  knowledge_progress: '掌握进度',
  discipline: '学习习惯',
};

const PROFILE_EMPTY_TEXT = {
  weak_points: '暂无错题或评测记录',
  knowledge_progress: '暂无评测记录',
  discipline: '暂无连续学习记录',
};

export default function StudentProfile() {
  const navigate = useNavigate();
  const { activeCourseId, courses } = useCourse();
  const { user, refreshUser } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [guidanceSubmitting, setGuidanceSubmitting] = useState(false);
  const [dialogueMessage, setDialogueMessage] = useState('');
  const [dialogueSubmitting, setDialogueSubmitting] = useState(false);
  const [dialogueError, setDialogueError] = useState('');
  const [profileError, setProfileError] = useState(null);
  const [refreshTask, setRefreshTask] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState('');
  const [refreshError, setRefreshError] = useState('');
  const [localGuidanceLevel, setLocalGuidanceLevel] = useState(
    user?.guidance_level || 'L2'
  );
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line react-hooks/purity -- relative time display needs current timestamp
  const [now, setNow] = useState(Date.now());

  // 追踪当前活跃的 courseId，用于竞态防护
  const activeCourseRef = useRef(activeCourseId);
  useEffect(() => {
    activeCourseRef.current = activeCourseId;
  }, [activeCourseId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNow(Date.now());
  }, [profileData]);

  // 从全局用户数据同步引导粒度（非课程画像）
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (user?.guidance_level) {
      setLocalGuidanceLevel(user.guidance_level);
    }
  }, [user?.guidance_level]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const fetchProfile = useCallback(async () => {
    if (!activeCourseId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setProfileData(null);
      setProfileError(null);
      const res = await profileService.getStudentProfile(activeCourseId);
      // 竞态防护：请求返回时 courseId 已变化，丢弃过期响应
      if (activeCourseRef.current !== activeCourseId) return;
      if (res.code === 200) {
        setProfileData(res.data);
      } else {
        setProfileError(res.message || '加载失败，请重试');
      }
    } catch (error) {
      // 竞态防护：请求返回时 courseId 已变化，丢弃过期响应
      if (activeCourseRef.current !== activeCourseId) return;
      console.error("Failed to fetch profile data:", error);
      setProfileError('加载失败，请重试');
    } finally {
      if (activeCourseRef.current === activeCourseId) setLoading(false);
    }
  }, [activeCourseId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: fetch on mount / course change
    fetchProfile();
  }, [fetchProfile]);

  useEffect(() => {
    if (!refreshTask?.task_id || refreshTask.status !== 'processing') return;

    let cancelled = false;
    let timeoutId;

    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(refreshTask.task_id);
        if (cancelled) return;

        const task = res.data || {};
        const status = task.status || 'processing';
        setRefreshTask({
          ...task,
          task_id: task.task_id || refreshTask.task_id,
          status,
        });

        if (status === 'completed') {
          setRefreshing(false);
          setRefreshError('');
          setRefreshMessage('画像已同步');
          await fetchProfile();
        } else if (status === 'failed' || status === 'partial') {
          setRefreshing(false);
          setRefreshMessage('');
          setRefreshError(task.error_message || '画像同步失败，请稍后重试');
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('画像同步任务查询失败:', err);
        setRefreshError('画像同步状态查询失败，正在重试');
        timeoutId = setTimeout(pollTask, 2000);
      }
    };

    timeoutId = setTimeout(pollTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [fetchProfile, refreshTask?.status, refreshTask?.task_id]);

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

  if (profileError) {
    return (
      <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
        <Navbar />
        <Sidebar />
        <main className="ml-0 lg:ml-64 pt-16">
          <div className="max-w-[1280px] mx-auto px-6 py-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
            <span className="material-symbols-outlined text-6xl text-slate-300 mb-6">error_outline</span>
            <h2 className="font-h1 text-2xl text-on-surface mb-3">{profileError}</h2>
            <button
              onClick={fetchProfile}
              className="px-6 py-2.5 bg-cyan-600 text-white rounded-xl font-bold hover:bg-cyan-700 transition-colors cursor-pointer"
            >
              重试
            </button>
          </div>
        </main>
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
    profile_dimensions = [],
  } = profile;

  // 姓名优先级：real_name → username → 兜底
  const displayName = user?.real_name || user?.username || '学生';
  const displayInitial = (user?.real_name || user?.username || '学').charAt(0);

  // 当前课程名：从 CourseContext 按 activeCourseId 查找
  const currentCourseName = courses.find(c => c.id === activeCourseId)?.name || '未选择';
  const courseNameById = (courseId) => courses.find(c => c.id === courseId)?.name || '';
  const profileFields = [
    { label: '学号 / 工号', value: user?.student_id || '未填写' },
    { label: '专业', value: user?.major || '未填写' },
    { label: '年级', value: user?.grade || '未填写' },
    { label: '引导粒度', value: user?.guidance_level || localGuidanceLevel || 'L2' },
  ];

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

  const isOpaqueId = (value) => (
    typeof value === 'string' && /^[a-f0-9]{16,32}$/i.test(value)
  );

  const labelValue = (value) => PROFILE_VALUE_LABELS[value] || value;

  const displayCourseSubject = (subject) => {
    if (!subject) return '';
    if (subject === activeCourseId) return currentCourseName;
    const matchedCourseName = courseNameById(subject);
    if (matchedCourseName) return matchedCourseName;
    return isOpaqueId(subject) ? '' : subject;
  };

  const disciplineBadgeView = {
    subject: displayCourseSubject(discipline_badge.subject),
    level: labelValue(discipline_badge.level),
    streakDays: Number(discipline_badge.streak_days || 0),
  };

  const handleGuidanceChange = async (level) => {
    if (guidanceSubmitting || localGuidanceLevel === level) return;

    const previousLevel = localGuidanceLevel;
    setLocalGuidanceLevel(level); // 乐观更新：立即切换 UI
    setGuidanceSubmitting(true);

    try {
      const res = await authService.updateMyInfo({ guidance_level: level });
      if (res.code === 200) {
        refreshUser(); // 静默同步全局用户数据
      } else {
        setLocalGuidanceLevel(previousLevel); // 失败回滚
      }
    } catch (err) {
      console.error('更新引导粒度失败:', err);
      setLocalGuidanceLevel(previousLevel); // 失败回滚
    } finally {
      setGuidanceSubmitting(false);
    }
  };

  const formatDisciplineDimension = (value) => {
    if (!value || typeof value !== 'object') return PROFILE_EMPTY_TEXT.discipline;

    const parts = [];
    const subject = displayCourseSubject(value.subject);
    const level = labelValue(value.level);
    const streakDays = Number(value.streak_days || 0);

    if (level) parts.push(`状态：${level}`);
    if (subject) parts.push(`课程：${subject}`);
    if (streakDays > 0) parts.push(`连续学习 ${streakDays} 天`);

    return parts.join(' · ') || PROFILE_EMPTY_TEXT.discipline;
  };

  const formatDimensionValue = (value, key) => {
    if (key === 'discipline') return formatDisciplineDimension(value);
    if (key === 'knowledge_progress' && !value) return PROFILE_EMPTY_TEXT.knowledge_progress;

    if (Array.isArray(value)) {
      return value.filter(Boolean).map(labelValue).join('、') || PROFILE_EMPTY_TEXT[key] || '待补充';
    }
    if (value && typeof value === 'object') {
      const meaningful = Object.entries(value)
        .filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined)
        .map(([itemKey, itemValue]) => `${itemKey}: ${labelValue(itemValue)}`);
      return meaningful.join(' / ') || PROFILE_EMPTY_TEXT[key] || '待补充';
    }
    if (value === 0) return '0';
    return labelValue(value) || PROFILE_EMPTY_TEXT[key] || '待补充';
  };

  const sourceLabel = (source) => ({
    profile_dialogue: '个人补充',
    system_profile: '系统分析',
    resource_usage: '学习行为',
    evaluation: '评测结果',
    activity: '学习记录',
    system_pending: '数据不足',
  }[source] || source || '未知来源');

  const handleProfileRefresh = async () => {
    if (!activeCourseId || refreshing) return;

    setRefreshing(true);
    setRefreshError('');
    setRefreshMessage('正在同步画像...');
    try {
      const res = await profileService.refreshProfile(activeCourseId);
      const taskId = res.data?.task_id;
      if (res.code === 202 && taskId) {
        setRefreshTask({ task_id: taskId, status: 'processing', progress: 10 });
      } else {
        setRefreshing(false);
        setRefreshMessage('');
        setRefreshError(res.message || '画像同步启动失败，请稍后重试');
      }
    } catch (err) {
      console.error('画像同步启动失败:', err);
      setRefreshing(false);
      setRefreshMessage('');
      setRefreshError(err.response?.data?.detail?.message || '画像同步启动失败，请稍后重试');
    }
  };

  const handleDialogueSubmit = async () => {
    const message = dialogueMessage.trim();
    if (!message || dialogueSubmitting) return;

    setDialogueSubmitting(true);
    setDialogueError('');
    try {
      const res = await profileService.updateProfileByDialogue(activeCourseId, message);
      if (res.code === 200) {
        const nextProfile = res.data?.profile_data;
        if (nextProfile) {
          setProfileData(nextProfile);
        } else {
          await fetchProfile();
        }
        setDialogueMessage('');
      } else {
        setDialogueError(res.message || '画像补充失败，请稍后重试');
      }
    } catch (err) {
      console.error('画像补充失败:', err);
      setDialogueError(err.response?.data?.detail?.message || '画像补充失败，请稍后重试');
    } finally {
      setDialogueSubmitting(false);
    }
  };

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
                {discipline_badge.level ? (
                  <span className="bg-amber-50 text-amber-700 text-xs px-4 py-1 rounded-full font-bold uppercase tracking-wider border border-amber-200">
                    学科勋章：{disciplineBadgeView.subject ? `${disciplineBadgeView.subject} · ` : ''}{disciplineBadgeView.level}
                  </span>
                ) : (
                  <span className="bg-slate-100 text-slate-400 text-xs px-4 py-1 rounded-full">学科勋章：—</span>
                )}
              </div>
              <p className="text-body-md text-secondary">当前进修课程：<span className="text-primary font-bold">{currentCourseName}</span></p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-5">
                {profileFields.map((field) => (
                  <div key={field.label} className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">{field.label}</p>
                    <p className="text-sm text-on-surface font-semibold truncate">{field.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
            <section className="lg:col-span-7 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
              <div className="flex items-center justify-between gap-4 mb-5">
                <div>
                  <h3 className="font-h3 text-xl flex items-center gap-2 text-on-surface">
                    <span className="material-symbols-outlined text-cyan-500">badge</span> 学习档案
                  </h3>
                  <p className="text-sm text-secondary mt-1">根据学习行为、评测结果和个人补充生成的课程学习档案。</p>
                </div>
                <button
                  onClick={handleProfileRefresh}
                  disabled={refreshing}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-600 text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-700 transition-colors"
                >
                  <span className={`material-symbols-outlined text-base ${refreshing ? 'animate-spin' : ''}`}>
                    {refreshing ? 'progress_activity' : 'sync'}
                  </span>
                  {refreshing ? '同步中...' : '同步画像'}
                </button>
              </div>
              {(refreshMessage || refreshError) && (
                <div className={`mb-4 rounded-xl border px-4 py-3 text-sm ${
                  refreshError
                    ? 'border-red-100 bg-red-50 text-red-600'
                    : 'border-cyan-100 bg-cyan-50 text-cyan-700'
                }`}>
                  {refreshError || refreshMessage}
                </div>
              )}
              {profile_dimensions.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {profile_dimensions.map((dimension) => (
                    <div key={dimension.key} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">
                          {PROFILE_DIMENSION_LABELS[dimension.key] || dimension.label}
                        </p>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-white text-cyan-700 border border-cyan-100">
                          {sourceLabel(dimension.source)}
                        </span>
                      </div>
                      <p className="text-sm text-on-surface font-semibold leading-6">
                        {formatDimensionValue(dimension.value, dimension.key)}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400 py-6 text-center">暂无画像维度数据</p>
              )}
            </section>

            <section className="lg:col-span-5 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
              <h3 className="font-h3 text-xl mb-2 flex items-center gap-2 text-on-surface">
                <span className="material-symbols-outlined text-cyan-500">edit_note</span> 补充学习画像
              </h3>
              <p className="text-sm text-secondary mb-4">
                用一句话说明目标、薄弱点或资源偏好，系统会补充到当前课程画像。
              </p>
              <textarea
                value={dialogueMessage}
                onChange={(event) => {
                  setDialogueMessage(event.target.value);
                  if (dialogueError) setDialogueError('');
                }}
                maxLength={1000}
                rows={5}
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-on-surface outline-none focus:border-cyan-400 focus:bg-white transition-colors resize-none"
                placeholder="例如：我想两周内补齐 C 语言指针和动态内存分配，最好多给代码练习。"
              />
              <div className="flex items-center justify-between mt-3">
                <span className={`text-xs ${dialogueError ? 'text-red-500' : 'text-slate-400'}`}>
                  {dialogueError || `${dialogueMessage.length}/1000`}
                </span>
                <button
                  onClick={handleDialogueSubmit}
                  disabled={!dialogueMessage.trim() || dialogueSubmitting}
                  className="px-4 py-2 rounded-xl bg-cyan-600 text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-700 transition-colors"
                >
                  {dialogueSubmitting ? '补充中...' : '补充画像'}
                </button>
              </div>
            </section>
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
              <p className="text-sm text-cyan-600 font-bold mt-2">
                当前等级：{['L1', 'L2', 'L3'].includes(localGuidanceLevel) ? localGuidanceLevel : '未知'}
              </p>
            </div>
            <div className="relative px-6 py-12 flex-1">
              <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden relative">
                <div className="h-full bg-gradient-to-r from-cyan-400 to-cyan-600 transition-all duration-500 ease-out" style={{ width: `${
                  localGuidanceLevel === 'L1' ? '0%' :
                  localGuidanceLevel === 'L2' ? '50%' :
                  localGuidanceLevel === 'L3' ? '100%' : '50%'
                }` }}></div>
              </div>
              <div className="flex justify-between items-center absolute w-full left-0 top-0 mt-[38px] px-4">
                <button
                  className="flex flex-col items-center cursor-pointer disabled:opacity-50 bg-transparent border-0 p-0"
                  onClick={() => handleGuidanceChange('L1')}
                  disabled={guidanceSubmitting}
                >
                  <div className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 transition-colors duration-300 ${
                    localGuidanceLevel === 'L1'
                      ? 'bg-cyan-500 border-white shadow-cyan-200'
                      : 'bg-white border-slate-200 hover:border-cyan-300'
                  }`}></div>
                  <div className="mt-6 text-center">
                    <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L1' ? 'text-cyan-600' : 'text-slate-400'}`}>L1: 启发点拨</p>
                    <p className="text-[10px] text-slate-400 mt-1">核心思路提示</p>
                  </div>
                </button>
                <button
                  className="flex flex-col items-center cursor-pointer disabled:opacity-50 bg-transparent border-0 p-0"
                  onClick={() => handleGuidanceChange('L2')}
                  disabled={guidanceSubmitting}
                >
                  <div className={`w-10 h-10 rounded-full border-[6px] shadow-xl z-20 transition-colors duration-300 ${
                    localGuidanceLevel === 'L2'
                      ? 'bg-cyan-500 border-white shadow-cyan-200'
                      : 'bg-white border-slate-200 shadow-sm hover:border-cyan-300'
                  }`}></div>
                  <div className="mt-4 text-center">
                    <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L2' ? 'text-cyan-600' : 'text-slate-400'}`}>L2: 伴学拆解</p>
                    <p className={`text-[10px] transition-colors duration-300 ${localGuidanceLevel === 'L2' ? 'text-cyan-400' : 'text-slate-400'} mt-1`}>分步引导学习</p>
                  </div>
                </button>
                <button
                  className="flex flex-col items-center cursor-pointer disabled:opacity-50 bg-transparent border-0 p-0"
                  onClick={() => handleGuidanceChange('L3')}
                  disabled={guidanceSubmitting}
                >
                  <div className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 transition-colors duration-300 ${
                    localGuidanceLevel === 'L3'
                      ? 'bg-cyan-500 border-white shadow-cyan-200'
                      : 'bg-white border-slate-200 hover:border-cyan-300'
                  }`}></div>
                  <div className="mt-6 text-center">
                    <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L3' ? 'text-cyan-600' : 'text-slate-400'}`}>L3: 保姆生成</p>
                    <p className="text-[10px] text-slate-400 mt-1">全自动代码生成</p>
                  </div>
                </button>
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
                    const isLearning = node.status === 'learning';
                    const colorClass = isMastered
                      ? 'bg-green-50 text-green-700 border-green-100'
                      : isLearning
                        ? 'bg-amber-50 text-amber-700 border-amber-100'
                        : 'bg-slate-100 text-slate-400 border-slate-200';
                    const icon = isMastered ? 'check_circle' : isLearning ? 'sync' : 'help';
                    const label = isMastered ? '已掌握' : isLearning ? '学习中' : '未知';
                    return (
                      <span
                        key={i}
                        className={`px-4 py-2 rounded-lg border text-sm font-bold flex items-center gap-2 transition-all hover:scale-105 ${colorClass}`}
                      >
                        <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: '"FILL" 1' }}>
                          {icon}
                        </span>
                        {node.name}
                        <span className="text-xs font-normal opacity-60">{label}</span>
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
                    const blindspot = typeof item === 'string' ? { name: item } : item;
                    const severityColors = {
                      high: 'bg-red-50 text-red-700 border-red-100',
                      medium: 'bg-amber-50 text-amber-700 border-amber-100',
                      low: 'bg-slate-100 text-slate-500 border-slate-200',
                    };
                    const severityLabels = { high: '高', medium: '中', low: '低' };
                    const colorClass = severityColors[blindspot.severity] || 'bg-slate-100 text-slate-500 border-slate-200';
                    const label = severityLabels[blindspot.severity] || blindspot.severity || '待关注';
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${colorClass} border`}>
                          {label}
                        </span>
                        <span className="text-sm text-on-surface">{blindspot.name || blindspot.point || '未命名薄弱点'}</span>
                        {blindspot.error_count !== undefined && (
                          <span className="text-xs text-slate-400">· 错误 {blindspot.error_count} 次</span>
                        )}
                        {blindspot.source === 'profile_dialogue' && (
                          <span className="text-xs text-cyan-600">· 对话补充</span>
                        )}
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
                    daily_homework: '课后巩固',
                    casual: '兴趣拓展',
                  }[drive_intent.type] || labelValue(drive_intent.type)}
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
              {discipline_badge.level ? (
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center border-4 border-amber-200">
                    <span className="material-symbols-outlined text-2xl text-amber-600" style={{ fontVariationSettings: '"FILL" 1' }}>
                      verified
                    </span>
                  </div>
                  <div>
                    <p className="font-bold text-on-surface">
                      学科勋章：{disciplineBadgeView.subject ? `${disciplineBadgeView.subject} · ` : ''}{disciplineBadgeView.level}
                    </p>
                    <p className="text-sm text-slate-500 mt-1">
                      连续学习 <span className="text-amber-600 font-bold">{disciplineBadgeView.streakDays}</span> 天
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
