import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import FeedbackStatus from '../components/FeedbackStatus';
import CreateCourseDialog from '../components/CreateCourseDialog';
import { useAuth } from '../context/AuthContext';
import Icon from '../components/Icon';
import { useTeacherConsoleData } from '../hooks/useTeacherConsoleData';

import ClassSelectorRow from '../components/teacher/ClassSelectorRow';
import TeacherResourceSection from '../components/teacher/TeacherResourceSection';
import StudentMonitoringSection from '../components/teacher/StudentMonitoringSection';
import ClassInsightsSection from '../components/teacher/ClassInsightsSection';

export default function TeacherConsole() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const roleLabelMap = { teacher: '教师', admin: '管理员' };
  const [activeClass, setActiveClass] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [pendingCreatedClassId, setPendingCreatedClassId] = useState(null);
  const [copiedCourseCode, setCopiedCourseCode] = useState(false);
  const [expandedChapter, setExpandedChapter] = useState(null);

  const {
    classes, classesLoading, refreshClasses,
    students, studentsLoading, studentsError,
    insights, insightsLoading, insightsError,
    resources, resourcesLoading, resourcesError
  } = useTeacherConsoleData(activeClass, { resourcePage: 1, resourcePageSize: 50 });

  const groupedResources = useMemo(() => {
    return resources.reduce((acc, resource) => {
      const chapter = resource.chapter || '未分类资源';
      if (!acc[chapter]) acc[chapter] = [];
      acc[chapter].push(resource);
      return acc;
    }, {});
  }, [resources]);

  useEffect(() => {
    const chapters = Object.keys(groupedResources).sort();
    if (chapters.length > 0 && (!expandedChapter || !chapters.includes(expandedChapter))) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setExpandedChapter(chapters[0]);
    }
  }, [groupedResources, expandedChapter]);

  useEffect(() => {
    if (classes.length > 0 && !activeClass) {
      if (pendingCreatedClassId && classes.some(c => c.id === pendingCreatedClassId)) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setActiveClass(pendingCreatedClassId);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setPendingCreatedClassId(null);
      } else {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setActiveClass(classes[0].id);
      }
    }
  }, [classes, activeClass, pendingCreatedClassId]);

  const handleCopyCourseCode = async () => {
    if (!activeClassInfo?.course_code) return;
    try {
      await navigator.clipboard.writeText(activeClassInfo.course_code);
    } catch {
      const el = document.createElement('textarea');
      el.value = activeClassInfo.course_code;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    setCopiedCourseCode(true);
    setTimeout(() => setCopiedCourseCode(false), 2000);
  };

  if (classesLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="loading" title="加载教学班列表..." />
      </div>
    );
  }

  if (!classesLoading && classes.length === 0) {
    return (
      <>
        <div className="min-h-screen w-full px-4 flex items-center justify-center bg-background flex-col gap-4">
          <FeedbackStatus status="empty" title="暂无教学班" description="请先选择已就绪课程资源库创建教学班" />
          <button
            onClick={() => setShowCreateDialog(true)}
            className="mt-4 px-5 py-2.5 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-full transition-colors whitespace-nowrap min-w-fit"
          >
            创建第一个教学班
          </button>
        </div>
        <CreateCourseDialog
          open={showCreateDialog}
          onClose={() => { setShowCreateDialog(false); refreshClasses(); }}
          onCreated={(createdClass) => {
            if (createdClass?.id) {
              setPendingCreatedClassId(createdClass.id);
            }
          }}
        />
      </>
    );
  }

  const activeClassInfo = classes.find((cls) => cls.id === activeClass);

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
            <div className="w-10 h-10 rounded-full bg-cyan-500/20 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-sm">
              {(user?.real_name || user?.username || '教').charAt(0)}
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-on-surface">{user?.real_name || user?.username || '教师'}</span>
              <span className="text-[10px] text-outline uppercase tracking-wider">
                {roleLabelMap[user?.role] || '教师'}
              </span>
            </div>
          </div>
          <div className="h-8 w-[1px] bg-outline-variant"></div>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-cyan-600 bg-cyan-50 hover:bg-cyan-100 rounded-lg transition-colors"
          >
            <Icon name="add" className="material-symbols-outlined text-sm"/>
            创建教学班
          </button>
          <div className="h-8 w-[1px] bg-outline-variant"></div>
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-error hover:bg-error-container/20 rounded-lg transition-colors" onClick={() => navigate('/')}>
            <Icon name="logout" className="material-symbols-outlined text-sm"/>
            退出登入
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 pt-20 px-gutter pb-xl overflow-y-auto">
        <div className="max-w-[1280px] mx-auto py-margin">
          
          {/* Class Selection Row */}
          <ClassSelectorRow 
            classes={classes} 
            activeClass={activeClass} 
            setActiveClass={setActiveClass} 
            activeClassInfo={activeClassInfo} 
          />

          {/* Class Learning Resources */}
          <TeacherResourceSection
            activeClassInfo={activeClassInfo}
            resourcesLoading={resourcesLoading}
            resourcesError={resourcesError}
            resources={resources}
            groupedResources={groupedResources}
            expandedChapter={expandedChapter}
            setExpandedChapter={setExpandedChapter}
            handleCopyCourseCode={handleCopyCourseCode}
            copiedCourseCode={copiedCourseCode}
            navigate={navigate}
          />

          {/* Student Monitoring Table */}
          <StudentMonitoringSection
            activeClassInfo={activeClassInfo}
            activeClass={activeClass}
            studentsLoading={studentsLoading}
            studentsError={studentsError}
            students={students}
            navigate={navigate}
          />

          {/* Class Statistics Section */}
          <ClassInsightsSection
            insightsLoading={insightsLoading}
            insightsError={insightsError}
            insights={insights}
          />

        </div>
      </main>

      <CreateCourseDialog
        open={showCreateDialog}
        onClose={() => { setShowCreateDialog(false); refreshClasses(); }}
        onCreated={(createdClass) => {
          if (createdClass?.id) {
            setPendingCreatedClassId(createdClass.id);
          }
        }}
      />
    </div>
  );
}
