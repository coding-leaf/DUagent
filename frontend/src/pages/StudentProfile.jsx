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
import ModalityPreferenceCard from '../components/profile/ModalityPreferenceCard';
import GuidanceLevelCard from '../components/profile/GuidanceLevelCard';
import KnowledgeRadarCard from '../components/profile/KnowledgeRadarCard';
import LearningStateCard from '../components/profile/LearningStateCard';

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
          <ModalityPreferenceCard modal_preference={modal_preference} />

          <GuidanceLevelCard 
            localGuidanceLevel={localGuidanceLevel}
            handleGuidanceChange={handleGuidanceChange}
            guidanceSubmitting={guidanceSubmitting}
            guidanceUpdatedText={guidanceUpdatedText}
          />

          <KnowledgeRadarCard
            knowledge_coordinates={knowledge_coordinates}
            cognitive_blindspots={cognitive_blindspots}
            daysAgoText={daysAgoText}
            labelValue={labelValue}
          />

          <LearningStateCard
            drive_intent={drive_intent}
            habits={habits}
            driveScore={driveScore}
            discipline_badge={discipline_badge}
            disciplineBadgeView={disciplineBadgeView}
            labelValue={labelValue}
          />

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
