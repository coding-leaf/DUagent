import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { teachingService } from '../api/services/teaching';
import { learningService } from '../api/services/learning';
import FeedbackStatus from '../components/FeedbackStatus';
import CreateCourseDialog from '../components/CreateCourseDialog';
import { useAuth } from '../context/AuthContext';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';
const RESOURCE_TYPE_OPTIONS = [
  { value: 'document', label: '文档' },
  { value: 'mindmap', label: '思维导图' },
  { value: 'reading', label: '阅读材料' },
  { value: 'code', label: '代码示例' },
];

const RESOURCE_TYPE_LABELS = RESOURCE_TYPE_OPTIONS.reduce((acc, option) => {
  acc[option.value] = option.label;
  return acc;
}, {});

const getErrorMessage = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.message) return detail.message;
  return error?.response?.data?.message || error?.message || fallback;
};

export default function TeacherConsole() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const resourcePollTimerRef = useRef(null);
  const roleLabelMap = { teacher: '教师', admin: '管理员' };
  const [activeClass, setActiveClass] = useState(null);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [insights, setInsights] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [classesLoading, setClassesLoading] = useState(true);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentsError, setStudentsError] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [insightsError, setInsightsError] = useState(null);
  const [resourceChapter, setResourceChapter] = useState('');
  const [resourceKnowledgePoint, setResourceKnowledgePoint] = useState('');
  const [selectedResourceTypes, setSelectedResourceTypes] = useState(() => RESOURCE_TYPE_OPTIONS.map(option => option.value));
  const [resourceTask, setResourceTask] = useState(null);
  const [resourceGenerating, setResourceGenerating] = useState(false);
  const [resourceGenerationError, setResourceGenerationError] = useState('');
  const [generatedResources, setGeneratedResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [resourcesError, setResourcesError] = useState('');

  const clearResourcePoll = useCallback(() => {
    if (resourcePollTimerRef.current) {
      clearTimeout(resourcePollTimerRef.current);
      resourcePollTimerRef.current = null;
    }
  }, []);

  // 获取班级列表
  const refreshClasses = useCallback(async (silent = false) => {
    if (!silent) setClassesLoading(true);
    try {
      const res = await teachingService.getClasses();
      if (res.code === 200) {
        const newClasses = res.data || [];
        setClasses(newClasses);
        setActiveClass(prev => {
          if (newClasses.length > 0 && !newClasses.find(c => c.id === prev)) {
            return newClasses[0].id;
          }
          return prev;
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      if (!silent) setClassesLoading(false);
    }
  }, []);

  const fetchGeneratedResources = useCallback(async (courseId) => {
    if (!courseId) return;
    setResourcesLoading(true);
    setResourcesError('');
    try {
      const res = await learningService.getResources({ course_id: courseId, page: 1, page_size: 20 });
      if (res.code !== 200) {
        throw new Error(res.message || '资源列表加载失败');
      }
      setGeneratedResources(res.data?.resources || []);
    } catch (error) {
      console.error('generated resources fetch error', error);
      setResourcesError(getErrorMessage(error, '资源列表加载失败'));
    } finally {
      setResourcesLoading(false);
    }
  }, []);

  const pollResourceTask = useCallback((taskId, courseId) => {
    clearResourcePoll();

    const poll = async () => {
      try {
        const res = await learningService.getTaskStatus(taskId);
        if (res.code !== 200) {
          throw new Error(res.message || '任务状态查询失败');
        }

        const task = res.data;
        setResourceTask(task);

        if (task.status === 'completed') {
          setResourceGenerating(false);
          clearResourcePoll();
          await fetchGeneratedResources(courseId);
          return;
        }

        if (task.status === 'failed') {
          setResourceGenerating(false);
          setResourceGenerationError(task.error_message || '资源生成失败');
          clearResourcePoll();
          return;
        }

        resourcePollTimerRef.current = setTimeout(poll, 2000);
      } catch (error) {
        console.error('resource task poll error', error);
        setResourceGenerating(false);
        setResourceGenerationError(getErrorMessage(error, '任务状态查询失败'));
        clearResourcePoll();
      }
    };

    poll();
  }, [clearResourcePoll, fetchGeneratedResources]);

  const toggleResourceType = (type) => {
    setSelectedResourceTypes(prev => (
      prev.includes(type)
        ? prev.filter(item => item !== type)
        : [...prev, type]
    ));
  };

  const handleGenerateResources = async () => {
    if (!activeClass) {
      setResourceGenerationError('请先选择课程');
      return;
    }
    if (selectedResourceTypes.length === 0) {
      setResourceGenerationError('请至少选择一种资源类型');
      return;
    }

    clearResourcePoll();
    setResourceGenerating(true);
    setResourceGenerationError('');
    setResourceTask(null);

    const payload = {
      course_id: activeClass,
      resource_types: selectedResourceTypes,
    };
    const chapter = resourceChapter.trim();
    const knowledgePoint = resourceKnowledgePoint.trim();
    if (chapter) payload.chapter = chapter;
    if (knowledgePoint) payload.knowledge_point = knowledgePoint;

    try {
      const res = await learningService.triggerResourceGeneration(payload);
      if (res.code !== 202 && res.code !== 200) {
        throw new Error(res.message || '资源生成任务创建失败');
      }

      const taskId = res.data?.task_id;
      if (!taskId) {
        throw new Error('资源生成任务缺少 task_id');
      }

      setResourceTask({
        task_id: taskId,
        task_type: 'resource_generation',
        status: 'processing',
        progress: 0,
      });
      pollResourceTask(taskId, activeClass);
    } catch (error) {
      console.error('resource generation error', error);
      setResourceGenerating(false);
      setResourceGenerationError(getErrorMessage(error, '资源生成任务创建失败'));
    }
  };

  useEffect(() => {
    refreshClasses(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [refreshClasses]);

  useEffect(() => {
    clearResourcePoll();
    const timer = setTimeout(() => {
      setResourceTask(null);
      setResourceGenerating(false);
      setResourceGenerationError('');
      fetchGeneratedResources(activeClass);
    }, 0);
    return () => clearTimeout(timer);
  }, [activeClass, clearResourcePoll, fetchGeneratedResources]);

  useEffect(() => clearResourcePoll, [clearResourcePoll]);

  // 当选择的班级改变时，获取学生列表和AI洞察
  useEffect(() => {
    if (!activeClass) return;

    setStudentsLoading(true); // eslint-disable-line react-hooks/set-state-in-effect
    setStudentsError(null);
    teachingService.getClassStudents(activeClass)
      .then((res) => {
        if (res.code === 200) setStudents(res.data);
      })
      .catch((err) => {
        console.error('students fetch error', err);
        setStudentsError('学生列表加载失败');
      })
      .finally(() => setStudentsLoading(false));

    setInsightsLoading(true);
    setInsightsError(null);
    teachingService.getConsoleInsights(activeClass)
      .then((res) => {
        if (res.code === 200) setInsights(res.data);
      })
      .catch((err) => {
        console.error('insights fetch error', err);
        setInsightsError('班级统计加载失败，请稍后重试。');
      })
      .finally(() => setInsightsLoading(false));
  }, [activeClass]);

  if (classesLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="loading" title="加载班级列表..." />
      </div>
    );
  }

  if (!classesLoading && classes.length === 0) {
    return (
      <>
        <div className="min-h-screen w-full px-4 flex items-center justify-center bg-background flex-col gap-4">
          <FeedbackStatus status="empty" title="暂无班级" description="您目前没有管理任何班级" />
          <button
            onClick={() => setShowCreateDialog(true)}
            className="mt-4 px-5 py-2.5 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-full transition-colors whitespace-nowrap min-w-fit"
          >
            创建第一门课程
          </button>
        </div>
        <CreateCourseDialog
          open={showCreateDialog}
          onClose={() => { setShowCreateDialog(false); refreshClasses(); }}
          onCreated={() => {}}
        />
      </>
    );
  }

  const activeClassInfo = classes.find((cls) => cls.id === activeClass);
  const activeClassLabel = activeClassInfo?.name || activeClass || '未选择课程';

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
            <span className="material-symbols-outlined text-sm">add</span>
            创建课程
          </button>
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

          {/* Resource Generation */}
          <section className="mb-margin">
            <div className="bg-white rounded-xl border border-outline-variant shadow-sm overflow-hidden">
              <div className="px-md py-4 border-b border-outline-variant flex flex-col gap-1 bg-surface-container-lowest">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">auto_awesome</span>
                  <h3 className="font-h3 text-xl text-on-surface">课程资源生成</h3>
                </div>
                <p className="text-sm text-outline">
                  当前课程：{activeClassLabel}
                  {activeClass && <span className="ml-2 font-mono text-xs">ID: {activeClass}</span>}
                </p>
              </div>
              <div className="p-md grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-6">
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-semibold text-on-surface">章节</span>
                      <input
                        value={resourceChapter}
                        onChange={(event) => setResourceChapter(event.target.value)}
                        className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm outline-none focus:border-primary"
                        placeholder="例如：树与二叉树"
                        type="text"
                      />
                    </label>
                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-semibold text-on-surface">知识点</span>
                      <input
                        value={resourceKnowledgePoint}
                        onChange={(event) => setResourceKnowledgePoint(event.target.value)}
                        className="w-full rounded-lg border border-outline-variant bg-white px-3 py-2 text-sm outline-none focus:border-primary"
                        placeholder="例如：二叉树遍历"
                        type="text"
                      />
                    </label>
                  </div>
                  <div>
                    <span className="text-sm font-semibold text-on-surface block mb-2">资源类型</span>
                    <div className="flex flex-wrap gap-2">
                      {RESOURCE_TYPE_OPTIONS.map((option) => {
                        const selected = selectedResourceTypes.includes(option.value);
                        return (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => toggleResourceType(option.value)}
                            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                              selected
                                ? 'border-primary bg-primary text-white'
                                : 'border-outline-variant bg-white text-on-surface hover:bg-surface-container-low'
                            }`}
                          >
                            <span className="material-symbols-outlined text-[18px]">
                              {selected ? 'check_circle' : 'radio_button_unchecked'}
                            </span>
                            {option.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div className="lg:w-72 flex flex-col justify-between gap-4">
                  <div className="rounded-lg border border-outline-variant bg-surface-container-lowest p-4 min-h-[132px]">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-on-surface">任务状态</span>
                      {resourceTask?.status && (
                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                          resourceTask.status === 'completed'
                            ? 'bg-green-100 text-green-700'
                            : resourceTask.status === 'failed'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-amber-100 text-amber-700'
                        }`}>
                          {resourceTask.status}
                        </span>
                      )}
                    </div>
                    {resourceGenerationError ? (
                      <p className="text-sm text-error">{resourceGenerationError}</p>
                    ) : resourceTask ? (
                      <div className="space-y-2">
                        <p className="text-xs font-mono text-outline break-all">{resourceTask.task_id}</p>
                        <div className="h-2 rounded-full bg-surface-container-high overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all"
                            style={{ width: `${resourceTask.status === 'completed' ? 100 : (resourceTask.progress || 0)}%` }}
                          />
                        </div>
                        <p className="text-xs text-outline">
                          进度 {resourceTask.status === 'completed' ? 100 : (resourceTask.progress || 0)}%
                        </p>
                      </div>
                    ) : (
                      <p className="text-sm text-outline">暂无任务</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerateResources}
                    disabled={resourceGenerating}
                    className={`w-full inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-bold transition-colors ${
                      resourceGenerating
                        ? 'cursor-not-allowed bg-surface-container-high text-outline'
                        : 'bg-cyan-600 text-white hover:bg-cyan-700'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[18px]">
                      {resourceGenerating ? 'hourglass_top' : 'play_arrow'}
                    </span>
                    {resourceGenerating ? '生成中' : '生成资源'}
                  </button>
                </div>
              </div>
              <div className="border-t border-outline-variant bg-surface-container-lowest px-md py-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="material-symbols-outlined text-primary text-xl flex-shrink-0">folder_open</span>
                    <div className="min-w-0">
                      <h4 className="font-semibold text-on-surface">当前课程资源</h4>
                      <p className="text-xs text-outline truncate">
                        {activeClassLabel}
                        {activeClass && <span className="ml-2 font-mono">ID: {activeClass}</span>}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => fetchGeneratedResources(activeClass)}
                    disabled={resourcesLoading}
                    className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold text-cyan-600 hover:bg-cyan-50 disabled:cursor-not-allowed disabled:text-outline"
                  >
                    <span className="material-symbols-outlined text-[16px]">refresh</span>
                    刷新
                  </button>
                </div>
                {resourcesLoading ? (
                  <div className="py-4">
                    <FeedbackStatus status="loading" title="加载资源列表..." />
                  </div>
                ) : resourcesError ? (
                  <div className="py-4">
                    <FeedbackStatus status="error" title={resourcesError} onRetry={() => fetchGeneratedResources(activeClass)} />
                  </div>
                ) : generatedResources.length === 0 ? (
                  <div className="py-4">
                    <FeedbackStatus status="empty" title="暂无资源" description="当前课程尚未生成学习资源" />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
                    {generatedResources.slice(0, 8).map((resource) => (
                      <button
                        key={resource.id}
                        type="button"
                        data-testid="teacher-resource-card"
                        onClick={() => navigate(`/resource/${resource.id}`)}
                        className="rounded-lg border border-outline-variant bg-white p-3 text-left transition-all hover:border-cyan-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-cyan-500 cursor-pointer"
                      >
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="px-2 py-0.5 rounded bg-cyan-50 text-cyan-700 text-[10px] font-bold">
                            {RESOURCE_TYPE_LABELS[resource.type] || resource.type || '资源'}
                          </span>
                          <span className="text-[10px] text-outline truncate max-w-[120px]">
                            {resource.chapter || '未标章节'}
                          </span>
                        </div>
                        <p className="font-semibold text-sm text-on-surface line-clamp-2 mb-1">{resource.title}</p>
                        <p className="text-xs text-outline line-clamp-2 mb-2">{resource.description || '暂无描述'}</p>
                        <div className="flex items-center gap-1 text-[10px] text-primary">
                          <span className="material-symbols-outlined text-[12px]">bookmark</span>
                          <span className="truncate">{resource.knowledge_point || '未标知识点'}</span>
                        </div>
                        <div className="mt-2 flex items-center justify-end gap-1 text-[10px] font-semibold text-cyan-600">
                          查看详情
                          <span className="material-symbols-outlined text-[12px]">arrow_forward</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
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

          {/* Class Statistics Section */}
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-margin">
            {insightsLoading ? (
              <div className="col-span-full py-8 flex justify-center">
                <FeedbackStatus status="loading" title="加载班级统计..." />
              </div>
            ) : insightsError ? (
              <div className="col-span-full py-8 flex justify-center">
                <FeedbackStatus status="error" title={insightsError} />
              </div>
            ) : !insights ? (
              <div className="col-span-full py-8 flex justify-center">
                <FeedbackStatus status="empty" title="暂无班级统计数据" />
              </div>
            ) : (
              <>
                {/* Avg Quiz Score */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-xl">quiz</span>
                    <span className="text-sm font-semibold text-outline">平均练习分</span>
                  </div>
                  <p className="text-3xl font-bold text-on-surface">
                    {insights.avg_quiz_score != null
                      ? insights.avg_quiz_score.toFixed(1)
                      : '暂无数据'}
                  </p>
                </div>

                {/* Total Quiz Attempts */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-xl">assignment</span>
                    <span className="text-sm font-semibold text-outline">练习次数</span>
                  </div>
                  <p className="text-3xl font-bold text-on-surface">
                    {insights.total_quiz_attempts}
                  </p>
                </div>

                {/* Weak Points Top */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md md:col-span-2 lg:col-span-1">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-error text-xl">warning</span>
                    <span className="text-sm font-semibold text-outline">薄弱知识点</span>
                  </div>
                  {insights.weak_points_top.length === 0 ? (
                    <p className="text-sm text-outline">暂无薄弱知识点</p>
                  ) : (
                    <ul className="space-y-2">
                      {insights.weak_points_top.map((wp) => (
                        <li key={wp.knowledge_point} className="text-sm">
                          <div className="flex justify-between items-center">
                            <span className="text-on-surface truncate max-w-[60%]">{wp.knowledge_point}</span>
                            <span className="text-error font-semibold">{Math.round(wp.error_rate * 100)}%</span>
                          </div>
                          <span className="text-xs text-outline">
                            错 {wp.error_count} / 共 {wp.total_attempts} 次
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Path Node Progress */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="material-symbols-outlined text-primary text-xl">route</span>
                    <span className="text-sm font-semibold text-outline">路径节点分布</span>
                  </div>
                  {insights.path_node_progress.total_nodes === 0 ? (
                    <p className="text-sm text-outline">暂无学习路径数据</p>
                  ) : (
                    <div className="space-y-2">
                      {[
                        { label: '已完成', key: 'completed', color: 'bg-green-500' },
                        { label: '进行中', key: 'in_progress', color: 'bg-blue-500' },
                        { label: '推荐', key: 'recommended', color: 'bg-amber-500' },
                        { label: '待开始', key: 'pending', color: 'bg-gray-400' },
                      ].map(({ label, key, color }) => (
                        <div key={key} className="flex items-center gap-2 text-sm">
                          <div className={`w-2.5 h-2.5 rounded-full ${color}`} />
                          <span className="text-on-surface-variant w-14">{label}</span>
                          <span className="font-semibold text-on-surface">{insights.path_node_progress[key]}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </section>

        </div>
      </main>

      <CreateCourseDialog
        open={showCreateDialog}
        onClose={() => { setShowCreateDialog(false); refreshClasses(); }}
        onCreated={() => {}}
      />
    </div>
  );
}
