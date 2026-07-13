import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { learningService } from '../api/services/learning';
import { useCourse } from '../context/CourseContext';
import FeedbackStatus from '../components/FeedbackStatus';
import Navbar from '../components/Navbar';
import JoinCourseDialog from '../components/JoinCourseDialog';
import Icon from '../components/Icon';

const RESOURCE_TYPES = [
  { value: '全部', label: '全部' },
  { value: 'lesson', label: '标准讲义' },
  { value: 'diagram', label: '知识图解' },
  { value: 'example', label: '代码示例' }
];

const TYPE_MAP = {
  lesson: { label: '标准讲义', icon: 'description', colorClass: 'text-blue-600 bg-blue-50 border-blue-100' },
  diagram: { label: '知识图解', icon: 'schema', colorClass: 'text-purple-600 bg-purple-50 border-purple-100' },
  example: { label: '代码示例', icon: 'code', colorClass: 'text-emerald-600 bg-emerald-50 border-emerald-100' },
  document: { label: '文档', icon: 'description', colorClass: 'text-blue-600 bg-blue-50 border-blue-100' },
  mindmap: { label: '思维导图', icon: 'schema', colorClass: 'text-purple-600 bg-purple-50 border-purple-100' },
  reading: { label: '阅读资料', icon: 'menu_book', colorClass: 'text-amber-600 bg-amber-50 border-amber-100' },
  code: { label: '代码', icon: 'code', colorClass: 'text-emerald-600 bg-emerald-50 border-emerald-100' },
  video: { label: '视频', icon: 'play_circle', colorClass: 'text-rose-600 bg-rose-50 border-rose-100' }
};

const getResourceTypeInfo = (type) => {
  return TYPE_MAP[type] || { label: type || '其他', icon: 'draft', colorClass: 'text-gray-600 bg-gray-50 border-gray-100' };
};

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCourseId, loading: courseLoading, changeCourse, refreshCourses } = useCourse();
  const [searchTerm, setSearchTerm] = useState(location.state?.search ?? '');
  const [selectedType, setSelectedType] = useState(location.state?.type ?? '全部');
  const [allResources, setAllResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showJoinDialog, setShowJoinDialog] = useState(false);

  const fetchResources = useCallback(async () => {
    if (!activeCourseId) return;
    try {
      setLoading(true);
      setError(false);
      const res = await learningService.getResources({
        course_id: activeCourseId,
        keyword: searchTerm || undefined,
        page: 1,
        page_size: 50,
      });
      if (res.code === 200 && res.data) {
        setAllResources(res.data.resources || []);
      }
    } catch (err) {
      console.error("Failed to fetch resources:", err);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [activeCourseId, searchTerm]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchResources();
  }, [fetchResources]);

  // Filter logic
  const filteredResources = allResources.filter(resource => {
    const safeSearchTerm = (searchTerm || '').toLowerCase();
    const matchesSearch = (resource.title || '').toLowerCase().includes(safeSearchTerm) ||
                          (resource.description && resource.description.toLowerCase().includes(safeSearchTerm)) ||
                          (resource.knowledge_point && resource.knowledge_point.toLowerCase().includes(safeSearchTerm)) ||
                          (resource.chapter && resource.chapter.toLowerCase().includes(safeSearchTerm));
    const matchesType = selectedType === '全部' || resource.type === selectedType;
    return matchesSearch && matchesType;
  });

  if (courseLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <FeedbackStatus status="loading" title="加载课程中..." />
      </div>
    );
  }

  if (!activeCourseId) {
    return (
      <>
        <div className="min-h-screen w-full px-4 flex flex-col items-center justify-center bg-background">
          <FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />
          <div className="flex justify-center mt-4">
            <button
              onClick={() => setShowJoinDialog(true)}
              className="px-5 py-2.5 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-full transition-colors whitespace-nowrap min-w-fit"
            >
              加入课程
            </button>
          </div>
        </div>
        <JoinCourseDialog
          open={showJoinDialog}
          onClose={() => setShowJoinDialog(false)}
          onJoined={async (newCourse) => {
            await refreshCourses();
            if (newCourse?.id) {
              changeCourse(newCourse.id);
            }
          }}
        />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-background text-on-background font-body-md antialiased overflow-x-hidden">
      {/* TopNavBar */}
      <Navbar searchTerm={searchTerm} onSearch={setSearchTerm} />

      {/* Main Content */}
      <main className="pt-24 pb-12 min-h-screen text-left">
        <div className="max-w-[1280px] mx-auto px-6 md:px-8">
          {/* Header Section */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-on-surface mb-2">资源库</h1>
            <p className="text-secondary text-sm">获取最新的课程学习资料、思维导图和实操代码。</p>
          </div>

          {/* Categories Filter */}
          <div className="flex flex-wrap gap-3 mb-8">
            {RESOURCE_TYPES.map(typeObj => (
              <button
                key={typeObj.value}
                onClick={() => setSelectedType(typeObj.value)}
                className={`px-5 py-2.5 rounded-full font-medium transition-all active:scale-95 cursor-pointer ${
                  selectedType === typeObj.value
                    ? 'bg-primary-container text-white shadow-md shadow-cyan-100'
                    : 'bg-white border border-outline-variant text-secondary hover:border-cyan-500 hover:text-cyan-600'
                }`}
              >
                {typeObj.label}
              </button>
            ))}
          </div>

          {/* Filter Feedback */}
          {(selectedType !== '全部' || searchTerm) && (
            <div className="mb-8 flex items-center gap-3 bg-surface-container-low p-4 rounded-xl border border-primary-container/30">
              <Icon name="filter_alt" className="material-symbols-outlined text-primary"/>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-on-surface-variant">当前筛选：</span>
                
                {selectedType !== '全部' && (
                  <span className="px-3 py-1 bg-primary text-white rounded-full text-xs font-medium flex items-center gap-1">
                    类型: {getResourceTypeInfo(selectedType).label}
                    <button onClick={() => setSelectedType('全部')} className="hover:text-primary-container flex items-center justify-center cursor-pointer">
                      <Icon name="close" className="material-symbols-outlined text-[14px]"/>
                    </button>
                  </span>
                )}

                {searchTerm && (
                  <span className="px-3 py-1 bg-cyan-100 text-cyan-800 border border-cyan-200 rounded-full text-xs font-medium flex items-center gap-1">
                    关键词: "{searchTerm}"
                    <button onClick={() => setSearchTerm('')} className="hover:text-cyan-600 flex items-center justify-center cursor-pointer">
                      <Icon name="close" className="material-symbols-outlined text-[14px]"/>
                    </button>
                  </span>
                )}

                <button
                  onClick={() => { setSelectedType('全部'); setSearchTerm(''); }}
                  className="text-primary hover:underline text-xs flex items-center ml-2 cursor-pointer"
                >
                  <Icon name="delete" className="material-symbols-outlined text-xs mr-1"/> 清除全部
                </button>
              </div>
            </div>
          )}

          {/* Resources Grid */}
          <div className="mb-8">
            {loading ? (
              <FeedbackStatus status="loading" title="加载资源中..." />
            ) : error ? (
              <FeedbackStatus status="error" title="加载失败" description="请检查网络连接或稍后重试" onRetry={fetchResources} />
            ) : filteredResources.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredResources.map(resource => {
                  const typeInfo = getResourceTypeInfo(resource.type);
                  return (
                    <div key={resource.id} data-testid="resource-card"
                      onClick={() => navigate(`/resource/${resource.id}`)}
                      className="bg-white rounded-xl border border-outline-variant p-6 shadow-sm hover:border-cyan-300 hover:shadow-md transition-all duration-200 flex flex-col justify-between cursor-pointer">
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-4">
                          <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1 ${typeInfo.colorClass}`}>
                            <Icon name={typeInfo.icon} className="material-symbols-outlined text-[12px]"/>
                            {typeInfo.label}
                          </span>
                          {resource.chapter && (
                            <span className="px-2 py-0.5 bg-slate-100 text-slate-600 text-[10px] rounded font-medium truncate max-w-[150px]">
                              {resource.chapter}
                            </span>
                          )}
                        </div>

                        <h3 className="text-lg font-bold text-on-surface mb-2">{resource.title}</h3>
                        <p className="text-secondary text-sm mb-4 leading-relaxed line-clamp-3">{resource.description || '暂无描述'}</p>

                        {resource.knowledge_point && (
                          <div className="flex items-center gap-1.5 mb-4">
                            <Icon name="bookmark" className="material-symbols-outlined text-xs text-primary"/>
                            <span className="text-xs text-primary font-medium">{resource.knowledge_point}</span>
                          </div>
                        )}
                      </div>

                      <div className="pt-4 border-t border-slate-50 flex items-center justify-between">
                        <div className="flex flex-wrap gap-1">
                          {(resource.tags || []).slice(0, 3).map((tag, i) => (
                            <span key={i} className="px-2 py-0.5 bg-surface-container text-on-surface-variant text-[10px] rounded-full">
                              {tag}
                            </span>
                          ))}
                        </div>
                        <div className="text-[10px] text-gray-400 font-medium">
                          浏览 {resource.view_count || 0} 次
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div data-testid="resources-empty">
                <FeedbackStatus status="empty" title="课程资源正在准备中" description="请稍后查看" />
              </div>
            )}
          </div>

          {/* Load More */}
          {filteredResources.length > 0 && (
            <div className="mt-12 flex flex-col items-center gap-4">
              <p className="text-xs text-gray-400">已显示全部 {filteredResources.length} 个资源</p>
            </div>
          )}
        </div>
      </main>

      {/* Contextual FAB */}
      <button
        onClick={() => navigate('/ai-chat')}
        className="fixed bottom-8 right-8 w-14 h-14 bg-cyan-500 text-white rounded-full shadow-2xl shadow-cyan-500/40 flex items-center justify-center hover:scale-110 active:scale-90 transition-all z-40 cursor-pointer"
      >
        <Icon name="chat_bubble" className="material-symbols-outlined text-2xl"/>
      </button>

    </div>
  );
}
