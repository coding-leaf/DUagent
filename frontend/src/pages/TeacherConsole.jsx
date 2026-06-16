import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { teachingService } from '../api/services/teaching';
import { learningService } from '../api/services/learning';
import FeedbackStatus from '../components/FeedbackStatus';
import CreateCourseDialog from '../components/CreateCourseDialog';
import { useAuth } from '../context/AuthContext';
import Icon from '../components/Icon';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';
const resourceTypeLabels = {
  document: '文档',
  reading: '阅读材料',
  code: '代码示例',
  mindmap: '思维导图',
  video: '视频',
};

export default function TeacherConsole() {
  const navigate = useNavigate();
  const { user } = useAuth();
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
  const [resources, setResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [resourcesError, setResourcesError] = useState(null);
  const [pendingCreatedClassId, setPendingCreatedClassId] = useState(null);
  const [copiedCourseCode, setCopiedCourseCode] = useState(false);
  const [expandedChapter, setExpandedChapter] = useState(null);

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
      setExpandedChapter(chapters[0]);
    }
  }, [groupedResources, expandedChapter]);

  // 获取教学班列表
  const refreshClasses = useCallback(async (silent = false) => {
    if (!silent) setClassesLoading(true);
    try {
      const res = await teachingService.getClasses();
      if (res.code === 200) {
        const newClasses = res.data || [];
        setClasses(newClasses);
        setActiveClass(prev => {
          if (pendingCreatedClassId && newClasses.some(c => c.id === pendingCreatedClassId)) {
            return pendingCreatedClassId;
          }
          if (newClasses.length > 0 && !newClasses.find(c => c.id === prev)) {
            return newClasses[0].id;
          }
          return prev;
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      if (pendingCreatedClassId) setPendingCreatedClassId(null);
      if (!silent) setClassesLoading(false);
    }
  }, [pendingCreatedClassId]);

  useEffect(() => {
    refreshClasses(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [refreshClasses]);

  // 当选择的教学班改变时，获取学生列表、AI洞察和学习资源
  useEffect(() => {
    if (!activeClass) return;

    let cancelled = false;
    setStudentsLoading(true); // eslint-disable-line react-hooks/set-state-in-effect
    setStudentsError(null);
    teachingService.getClassStudents(activeClass)
      .then((res) => {
        if (!cancelled && res.code === 200) setStudents(res.data);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('students fetch error', err);
        setStudentsError('学生列表加载失败');
      })
      .finally(() => {
        if (!cancelled) setStudentsLoading(false);
      });

    setInsightsLoading(true);
    setInsightsError(null);
    teachingService.getConsoleInsights(activeClass)
      .then((res) => {
        if (!cancelled && res.code === 200) setInsights(res.data);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('insights fetch error', err);
        setInsightsError('班级统计加载失败，请稍后重试。');
      })
      .finally(() => {
        if (!cancelled) setInsightsLoading(false);
      });

    setResourcesLoading(true);
    setResourcesError(null);
    learningService.getResources({ course_id: activeClass, page: 1, page_size: 50 })
      .then((res) => {
        if (!cancelled && res.code === 200) {
          setResources(res.data?.resources || []);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('resources fetch error', err);
        setResourcesError('学习资源加载失败，请稍后重试。');
        setResources([]);
      })
      .finally(() => {
        if (!cancelled) setResourcesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeClass]);

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
          <section className="mb-margin">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-h3 text-xl text-on-surface">教学班选择</h3>
              <span className="text-sm text-outline">当前：{activeClassInfo?.name || activeClass}</span>
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
                      <Icon name="check_circle" className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: '"FILL" 1' }}/>
                    )}
                  </div>
                  <p className="font-h3 text-lg text-on-surface mb-1">{cls.topic}</p>
                  {cls.catalog_title && (
                    <p className="text-xs text-outline mb-1 line-clamp-1">资源库：{cls.catalog_title}</p>
                  )}
                  {cls.course_code && (
                    <p className="text-xs font-medium text-cyan-700 mb-1">课程码：{cls.course_code}</p>
                  )}
                  <p className="text-sm text-outline">{cls.students} 名学生</p>
                </button>
              ))}
            </div>
          </section>

          {/* Class Learning Resources */}
          <section className="mb-margin" data-testid="teacher-resource-section">
            <div className="bg-white rounded-xl border border-outline-variant shadow-sm overflow-hidden">
              <div className="px-md py-4 border-b border-outline-variant flex justify-between items-center bg-surface-container-lowest">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Icon name="library_books" className="material-symbols-outlined text-primary"/>
                    <h3 className="font-h3 text-xl text-on-surface">本班学习资源</h3>
                  </div>
                  {activeClassInfo?.course_code && (
                    <div className="flex items-center gap-2 text-xs text-outline">
                      <span className="font-semibold text-slate-600">课程码：{activeClassInfo.course_code}</span>
                      <button
                        type="button"
                        onClick={handleCopyCourseCode}
                        className="rounded-md bg-cyan-50 px-2 py-1 font-semibold text-cyan-700 hover:bg-cyan-100 transition-colors"
                      >
                        {copiedCourseCode ? '已复制' : '复制'}
                      </button>
                    </div>
                  )}
                </div>
                <span className="text-xs font-semibold text-outline">
                  {activeClassInfo?.catalog_title
                    ? `绑定资源库：${activeClassInfo.catalog_title}`
                    : '未绑定课程资源库'}
                </span>
              </div>

              <div className="p-md max-h-[500px] overflow-y-auto custom-scrollbar">
                {resourcesLoading ? (
                  <div className="py-8 flex justify-center">
                    <FeedbackStatus status="loading" title="加载学习资源..." />
                  </div>
                ) : resourcesError ? (
                  <div className="py-8 flex justify-center">
                    <FeedbackStatus status="error" title={resourcesError} />
                  </div>
                ) : resources.length === 0 ? (
                  <div className="py-8 flex justify-center">
                    <FeedbackStatus status="empty" title="本班暂无学习资源，请联系管理员生成" />
                  </div>
                ) : (
                  <div className="space-y-3">
                    {Object.keys(groupedResources).sort().map((chapter) => {
                      const isExpanded = expandedChapter === chapter;
                      const chapterResources = groupedResources[chapter];
                      return (
                        <div key={chapter} className="border border-outline-variant rounded-xl overflow-hidden bg-surface-container-lowest transition-all duration-200">
                          <button
                            type="button"
                            onClick={() => setExpandedChapter(isExpanded ? null : chapter)}
                            className="w-full flex items-center justify-between p-4 bg-cyan-50/40 hover:bg-cyan-50 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              <span className="font-semibold text-on-surface text-lg">{chapter}</span>
                              <span className="px-2.5 py-0.5 rounded-full bg-cyan-100/80 text-cyan-800 text-xs font-bold">
                                {chapterResources.length} 篇
                              </span>
                            </div>
                            <Icon name="expand_more" className={`material-symbols-outlined text-outline transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}/>
                          </button>
                          
                          {isExpanded && (
                            <div className="p-4 border-t border-outline-variant bg-white">
                              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                                {chapterResources.map((resource) => (
                                  <button
                                    key={resource.id}
                                    type="button"
                                    data-testid="teacher-resource-card"
                                    onClick={() => navigate(`/resource/${resource.id}`)}
                                    className="text-left rounded-xl border border-outline-variant bg-surface-container-lowest p-4 hover:border-primary/50 hover:shadow-sm transition-all group"
                                  >
                                    <div className="flex items-start justify-between gap-3 mb-3">
                                      <div>
                                        <p className="font-semibold text-on-surface line-clamp-1 group-hover:text-primary transition-colors">{resource.title}</p>
                                        <p className="text-xs text-outline mt-1">
                                          {resourceTypeLabels[resource.type] || resource.type || '资源'}
                                        </p>
                                      </div>
                                      <Icon name="open_in_new" className="material-symbols-outlined text-outline group-hover:text-primary text-lg transition-colors"/>
                                    </div>
                                    {resource.description && (
                                      <p className="text-sm text-on-surface-variant line-clamp-2 mb-3">{resource.description}</p>
                                    )}
                                    <div className="flex flex-wrap gap-2 text-xs text-outline">
                                      {resource.knowledge_point && (
                                        <span className="px-2 py-1 rounded bg-surface-container-high truncate max-w-full">知识点：{resource.knowledge_point}</span>
                                      )}
                                    </div>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
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
                  <Icon name="monitoring" className="material-symbols-outlined text-primary"/>
                  <h3 className="font-h3 text-xl text-on-surface">{activeClassInfo?.name || activeClass} 学生实时监控</h3>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center bg-surface-container-low rounded-lg px-3 py-1.5 border border-outline-variant">
                    <Icon name="search" className="material-symbols-outlined text-outline text-sm mr-2"/>
                    <input className="bg-transparent border-none focus:ring-0 text-sm w-32 outline-none" placeholder="搜索学生..." type="text" />
                  </div>
                  <button className="p-2 rounded-lg hover:bg-surface-container transition-colors">
                    <Icon name="refresh" className="material-symbols-outlined text-outline"/>
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
                <span className="text-xs font-medium text-outline">当前显示 {activeClassInfo?.name || activeClass} (42名学生中展示 14名)</span>
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
                    <Icon name="quiz" className="material-symbols-outlined text-primary text-xl"/>
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
                    <Icon name="assignment" className="material-symbols-outlined text-primary text-xl"/>
                    <span className="text-sm font-semibold text-outline">练习次数</span>
                  </div>
                  <p className="text-3xl font-bold text-on-surface">
                    {insights.total_quiz_attempts}
                  </p>
                </div>

                {/* Weak Points Top */}
                <div className="bg-white rounded-xl border border-outline-variant shadow-sm p-md md:col-span-2 lg:col-span-1">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="warning" className="material-symbols-outlined text-error text-xl"/>
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
                    <Icon name="route" className="material-symbols-outlined text-primary text-xl"/>
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
        onCreated={(createdClass) => {
          if (createdClass?.id) {
            setPendingCreatedClassId(createdClass.id);
          }
        }}
      />
    </div>
  );
}
