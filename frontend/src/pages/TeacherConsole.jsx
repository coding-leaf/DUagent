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
import { isMockEnabled } from '../api/mock';

const STUDENT_PAGE_SIZE = 14;

export default function TeacherConsole() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const roleLabelMap = { teacher: '教师', admin: '管理员' };
  const isMockMode = isMockEnabled;
  const [activeClass, setActiveClass] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [pendingCreatedClassId, setPendingCreatedClassId] = useState(null);
  const [copiedCourseCode, setCopiedCourseCode] = useState(false);
  const [expandedChapter, setExpandedChapter] = useState(null);
  const [studentSearchQuery, setStudentSearchQuery] = useState('');
  const [studentCurrentPage, setStudentCurrentPage] = useState(1);

  const {
    classes, classesLoading, refreshClasses,
    students, studentsLoading, studentsError, refreshStudents,
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
        /* eslint-disable react-hooks/set-state-in-effect */
        setActiveClass(pendingCreatedClassId);
        setPendingCreatedClassId(null);
        /* eslint-enable react-hooks/set-state-in-effect */
      } else {
        setActiveClass(classes[0].id);
      }
    }
  }, [classes, activeClass, pendingCreatedClassId]);

  // --- Derived State for Students ---
  const filteredStudents = useMemo(() => {
    const validStudents = students || [];
    if (!studentSearchQuery) return validStudents;
    const lowerQuery = studentSearchQuery.toLowerCase();
    return validStudents.filter(s => 
      (s.username ?? '').toLowerCase().includes(lowerQuery) ||
      (s.english_name ?? '').toLowerCase().includes(lowerQuery) ||
      (s.student_id ?? '').toLowerCase().includes(lowerQuery)
    );
  }, [students, studentSearchQuery]);

  const studentTotalPages = Math.max(1, Math.ceil(filteredStudents.length / STUDENT_PAGE_SIZE));
  const paginatedStudents = useMemo(() => {
    const startIndex = (studentCurrentPage - 1) * STUDENT_PAGE_SIZE;
    return filteredStudents.slice(startIndex, startIndex + STUDENT_PAGE_SIZE);
  }, [filteredStudents, studentCurrentPage]);

  // --- Effects ---
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setStudentCurrentPage(1);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [activeClass]);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setStudentCurrentPage(1);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [studentSearchQuery]);

  // --- Handlers ---
  const handleStudentClick = (studentId) => {
    navigate(`/teacher/report?course_id=${activeClass}&student_id=${studentId}`);
  };

  const handleResourceClick = (resourceId) => {
    navigate(`/resource/${resourceId}`);
  };

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
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur-md font-['Public_Sans'] antialiased">
        <div className="mx-auto flex min-h-20 max-w-[1280px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-cyan-700">
              <Icon name="school" className="material-symbols-outlined text-base" />
              教学控制台
            </div>
            <div className="flex min-w-0 items-baseline gap-3">
              <h1 data-testid="teacher-console-title" className="truncate text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
                {activeClassInfo?.name || '教学班管理'}
              </h1>
              <span className="hidden truncate text-sm text-slate-500 lg:inline">
                {activeClassInfo?.catalog_title || '课程教学管理'}
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-2 rounded-full bg-slate-50 py-1.5 pl-1.5 pr-3 md:flex">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-cyan-200 bg-cyan-100 text-sm font-bold text-cyan-700">
                {(user?.real_name || user?.username || '教').charAt(0)}
              </div>
              <div className="leading-tight">
                <p className="text-xs font-bold text-slate-800">{user?.real_name || user?.username || '教师'}</p>
                <p className="text-[10px] text-slate-500">{roleLabelMap[user?.role] || '教师'}</p>
              </div>
            </div>
            <button
              onClick={() => setShowCreateDialog(true)}
              className="flex cursor-pointer items-center gap-1.5 rounded-xl bg-cyan-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-cyan-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-offset-2 sm:px-4 sm:text-sm"
            >
              <Icon name="add" className="material-symbols-outlined text-sm"/>
              <span className="hidden sm:inline">创建教学班</span>
            </button>
            <button
              aria-label="退出登录"
              title="退出登录"
              className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              onClick={() => navigate('/')}
            >
              <Icon name="logout" className="material-symbols-outlined text-sm"/>
              <span className="hidden lg:inline">退出登录</span>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 pb-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1280px] py-6 sm:py-8">
          <ClassSelectorRow
            classes={classes}
            activeClass={activeClass}
            setActiveClass={setActiveClass}
            activeClassInfo={activeClassInfo}
          />

          <ClassInsightsSection
            insightsLoading={insightsLoading}
            insightsError={insightsError}
            insights={insights}
            studentCount={students.length}
            resourceCount={resources.length}
          />

          <StudentMonitoringSection
            activeClassInfo={activeClassInfo}
            activeClass={activeClass}
            studentsLoading={studentsLoading}
            studentsError={studentsError}
            students={paginatedStudents}
            searchQuery={studentSearchQuery}
            onSearchChange={setStudentSearchQuery}
            onRefresh={() => refreshStudents?.()}
            onStudentClick={handleStudentClick}
            totalStudents={filteredStudents.length}
            currentPage={studentCurrentPage}
            totalPages={studentTotalPages}
            onPageChange={setStudentCurrentPage}
            navigate={navigate}
            isMockMode={isMockMode}
          />

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
            onResourceClick={handleResourceClick}
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
