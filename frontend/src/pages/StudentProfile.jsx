import { useState, useEffect } from 'react';
import { useStudentProfile } from '../hooks/useStudentProfile';
import { useNavigate } from 'react-router-dom';
import { profileService } from '../api/services/profile';
import { authService } from '../api/services/auth';
import { useCourse } from '../context/CourseContext';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';
import Icon from '../components/Icon';
import ProfileHeaderCard from '../components/profile/ProfileHeaderCard';
import LearningArchiveCard from '../components/profile/LearningArchiveCard';
import LearningDirectionCard from '../components/profile/LearningDirectionCard';

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
  steady: '稳步提升',
  advanced: '进阶掌握',
  excellent: '表现优秀',
  active: '稳定学习',
  focused: '高频投入',
};

const PROFILE_EMPTY_TEXT = {
  weak_points: '暂无错题或评测记录',
  knowledge_progress: '暂无评测记录',
  discipline: '暂无连续学习记录',
  learning_habits: '暂无学习记录',
};

export default function StudentProfile() {
  const navigate = useNavigate();
  const { activeCourseId, courses } = useCourse();
  const { user, refreshUser } = useAuth();
  const [guidanceSubmitting, setGuidanceSubmitting] = useState(false);
  const [customInstruction, setCustomInstruction] = useState('');
  const [instructionSubmitting, setInstructionSubmitting] = useState(false);
  const [instructionError, setInstructionError] = useState('');
  const [instructionSuccess, setInstructionSuccess] = useState(false);
  const [goalSubmitting, setGoalSubmitting] = useState(false);
  const [localGuidanceLevel, setLocalGuidanceLevel] = useState(
    user?.guidance_level || 'L2'
  );

  const {
    profileData,
    profileLoading: loading,
    profileError,
    mutateProfile,
    refreshTask,
    isPolling: refreshing,
    handleProfileRefresh
  } = useStudentProfile(activeCourseId);

  // Sync instruction when profile loads
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const ci = profileData?.drive_intent?.custom_instruction;
    if (typeof ci === 'string') setCustomInstruction(ci);
  }, [profileData]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Map refresh statuses
  const refreshMessage = refreshTask?.status === 'completed' ? '画像已同步' : (refreshing ? '正在同步画像...' : '');
  const refreshError = refreshTask?.status === 'failed' ? (refreshTask?.error_message || '同步失败') : '';

  // eslint-disable-next-line react-hooks/purity -- relative time display needs current timestamp
  const [now, setNow] = useState(Date.now());

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

  if (!activeCourseId) {
    return (
      <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
        <Navbar />
        <main className="pt-16">
          <div className="max-w-[1280px] mx-auto px-6 py-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
            <Icon name="person_search" className="material-symbols-outlined text-6xl text-slate-300 mb-6"/>
            <h2 className="font-h1 text-2xl text-on-surface mb-3">还没有可查看的课程画像</h2>
            <p className="text-body-md text-secondary max-w-[448px] mb-8">
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
        <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-cyan-500"/>
      </div>
    );
  }

  if (profileError) {
    return (
      <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
        <Navbar />
        <main className="pt-16">
          <div className="max-w-[1280px] mx-auto px-6 py-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
            <Icon name="error_outline" className="material-symbols-outlined text-6xl text-slate-300 mb-6"/>
            <h2 className="font-h1 text-2xl text-on-surface mb-3">{profileError}</h2>
            <button
              onClick={mutateProfile}
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

  const habits = drive_intent.learning_habits ?? {};
  const streakScore = Math.min((habits.streak_days ?? 0) / 7, 1.0) * 100;
  const activeScore = ((habits.active_days_7d ?? 0) / 7) * 100;
  const hoursSince = habits.last_activity_at
    ? (now - new Date(habits.last_activity_at)) / 3600000
    : Infinity;
  const recencyScore = hoursSince <= 24 ? 100 : hoursSince <= 72 ? 70 : hoursSince <= 168 ? 40 : 0;
  const driveScore = Math.round(streakScore * 0.40 + activeScore * 0.40 + recencyScore * 0.20);

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

  const formatProfileTextValue = (value) => {
    if (typeof value !== 'string') return labelValue(value);
    const parts = value
      .split(/[、,/]/)
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length <= 1) return labelValue(value);
    return parts.map(labelValue).join('、');
  };

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
    
    if (key === 'knowledge_progress' && value && typeof value === 'object') {
      return `已掌握 ${value.mastered_nodes || 0}/${value.total_nodes || 0}，薄弱 ${value.weak_nodes || 0} 个，待练习 ${value.pending_nodes || 0} 个`;
    }
    
    if (key === 'learning_habits') {
      if (!value || typeof value !== 'object' || Object.keys(value).length === 0) {
        return PROFILE_EMPTY_TEXT.learning_habits;
      }
      const labelMap = { new: '新生', inactive: '不活跃', sprint: '突击', stable: '稳定', casual: '随性' };
      const label = labelMap[value.label] || value.label || '暂无学习记录';
      return `状态：${label} · 习惯分：${value.score || 0}`;
    }

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
    return formatProfileTextValue(value) || PROFILE_EMPTY_TEXT[key] || '待补充';
  };

  const sourceLabel = (source) => ({
    profile_dialogue: '个人补充',
    system_profile: '系统分析',
    resource_usage: '学习行为',
    evaluation: '评测结果',
    activity: '学习记录',
    system_pending: '数据不足',
    kg_quiz_activity: '图谱+行为',
  }[source] || source || '未知来源');

  const handleGoalChange = async (goalType) => {
    if (goalSubmitting) return;
    setGoalSubmitting(true);
    try {
      await profileService.updateLearningGoal(activeCourseId, goalType);
      mutateProfile();
    } catch (err) {
      console.error('更新学习方向失败:', err);
    } finally {
      setGoalSubmitting(false);
    }
  };

  const handleInstructionSubmit = async () => {
    if (instructionSubmitting) return;
    setInstructionSubmitting(true);
    setInstructionError('');
    setInstructionSuccess(false);
    try {
      const res = await profileService.updateCustomInstruction(activeCourseId, customInstruction.trim());
      if (res.code === 200) {
        setInstructionSuccess(true);
        setTimeout(() => setInstructionSuccess(false), 3000);
      } else {
        setInstructionError(res.message || '保存失败，请稍后重试');
      }
    } catch (err) {
      console.error('保存个性化偏好失败:', err);
      setInstructionError(err.response?.data?.detail?.message || '保存失败，请稍后重试');
    } finally {
      setInstructionSubmitting(false);
    }
  };

  return (
    <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
      {/* TopNavBar */}
      <Navbar />

      {/* Main Content */}
      <main className="pt-16">
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          <ProfileHeaderCard
            displayInitial={displayInitial}
            displayName={displayName}
            discipline_badge={discipline_badge}
            disciplineBadgeView={disciplineBadgeView}
            currentCourseName={currentCourseName}
            profileFields={profileFields}
          />

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
            <LearningArchiveCard
              handleProfileRefresh={handleProfileRefresh}
              refreshing={refreshing}
              refreshMessage={refreshMessage}
              refreshError={refreshError}
              profile_dimensions={profile_dimensions}
              formatDimensionValue={formatDimensionValue}
              sourceLabel={sourceLabel}
            />

            <LearningDirectionCard
              drive_intent={drive_intent}
              handleGoalChange={handleGoalChange}
              goalSubmitting={goalSubmitting}
              customInstruction={customInstruction}
              setCustomInstruction={(val) => {
                setCustomInstruction(val);
                if (instructionError) setInstructionError('');
                if (instructionSuccess) setInstructionSuccess(false);
              }}
              handleInstructionSubmit={handleInstructionSubmit}
              instructionSubmitting={instructionSubmitting}
              instructionError={instructionError}
              instructionSuccess={instructionSuccess}
            />
          </div>

        {/* Bento Grid Main Content */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-6">
          {/* 卡片 2：模态偏好 */}
          <div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
              <Icon name="pie_chart" className="material-symbols-outlined text-cyan-500"/> 模态偏好
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
                <Icon name="tune" className="material-symbols-outlined text-cyan-500"/> 引导粒度
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
                    <p className={`text-label-sm font-bold transition-colors duration-300 ${localGuidanceLevel === 'L3' ? 'text-cyan-600' : 'text-slate-400'}`}>L3: 逐步指导</p>
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
              <Icon name="grid_view" className="material-symbols-outlined text-cyan-500"/> 知识坐标 &amp; 认知盲区
            </h3>

            {/* 上半：知识坐标 */}
            <div className="mb-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">知识坐标</p>
              {knowledge_coordinates.length > 0 ? (
                <div className="flex flex-wrap gap-3">
                  {knowledge_coordinates.map((node, i) => {
                    const state = node.status || 'unstarted';
                    const stateConfig = {
                      mastered: {
                        color: 'bg-green-50 text-green-700 border-green-100',
                        icon: 'check_circle',
                        label: '已掌握',
                      },
                      weak: {
                        color: 'bg-red-50 text-red-700 border-red-100',
                        icon: 'warning',
                        label: '薄弱',
                      },
                      learning: {
                        color: 'bg-amber-50 text-amber-700 border-amber-100',
                        icon: 'sync',
                        label: '学习中',
                      },
                      pending_practice: {
                        color: 'bg-cyan-50 text-cyan-700 border-cyan-100',
                        icon: 'quiz',
                        label: '待练习',
                      },
                      unstarted: {
                        color: 'bg-slate-100 text-slate-500 border-slate-200',
                        icon: 'radio_button_unchecked',
                        label: '未开始',
                      },
                    }[state] || {
                      color: 'bg-slate-100 text-slate-500 border-slate-200',
                      icon: 'help',
                      label: labelValue(state) || '未知',
                    };
                    return (
                      <span
                        key={i}
                        className={`px-4 py-2 rounded-lg border text-sm font-bold flex items-center gap-2 transition-all hover:scale-105 ${stateConfig.color}`}
                      >
                        <Icon name={stateConfig.icon} className="material-symbols-outlined text-base" style={{ fontVariationSettings: '"FILL" 1' }}/>
                        {node.name}
                        <span className="text-xs font-normal opacity-60">{stateConfig.label}</span>
                        {state === 'mastered' && node.mastered_at && (
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
              <Icon name="psychology" className="material-symbols-outlined text-cyan-500"/> 学习状态
            </h3>

            {/* 驱动力 */}
            <div className="mb-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">驱动力</p>
              <div className="flex items-center gap-2 mb-3">
                <span className="px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg text-sm font-bold border border-cyan-100">
                  {{
                    exam_sprint: '备考冲刺',
                    daily_homework: '课后巩固',
                    casual: '兴趣拓展',
                  }[drive_intent.type] || labelValue(drive_intent.type)}
                </span>
                {habits.label && (
                  <span className="px-3 py-1.5 rounded-lg text-sm font-bold border {{
                    new: 'bg-slate-50 text-slate-500 border-slate-200',
                    inactive: 'bg-red-50 text-red-500 border-red-100',
                    sprint: 'bg-orange-50 text-orange-600 border-orange-100',
                    stable: 'bg-green-50 text-green-700 border-green-100',
                    casual: 'bg-slate-50 text-slate-500 border-slate-200',
                  }[habits.label] || 'bg-slate-50 text-slate-500 border-slate-200'}">
                    {{
                      new: '新生',
                      inactive: '不活跃',
                      sprint: '突击',
                      stable: '稳定',
                      casual: '随性',
                    }[habits.label] || habits.label}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${driveScore}%` }}></div>
                  </div>
                </div>
                <span className="text-xs text-slate-500 font-bold w-8 text-right">{driveScore}%</span>
              </div>
            </div>

            {/* 学科勋章 */}
            <div className="border-t border-slate-100 pt-6">
              <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">学科勋章</p>
              {discipline_badge.level ? (
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center border-4 border-amber-200">
                    <Icon name="verified" className="material-symbols-outlined text-2xl text-amber-600" style={{ fontVariationSettings: '"FILL" 1' }}/>
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
          <Icon name="account_tree" className="material-symbols-outlined"/>
          <span className="text-[10px] font-bold">学习</span>
        </button>
        <button onClick={() => navigate('/dashboard')} className="flex flex-col items-center gap-1 text-slate-400 cursor-pointer">
          <Icon name="library_books" className="material-symbols-outlined"/>
          <span className="text-[10px] font-bold">资源</span>
        </button>
        <div className="w-12 h-12 bg-cyan-600 rounded-full flex items-center justify-center text-white -mt-8 shadow-lg shadow-cyan-200">
          <Icon name="add" className="material-symbols-outlined"/>
        </div>
        <button onClick={() => navigate('/profile')} className="flex flex-col items-center gap-1 text-cyan-600 cursor-pointer">
          <Icon name="account_circle" className="material-symbols-outlined"/>
          <span className="text-[10px] font-bold">我的</span>
        </button>
      </footer>
    </div>
  );
}
