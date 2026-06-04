import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import TrainingReportModal from '../components/TrainingReportModal';
import { learningService } from '../api/services/learning';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';

const CATEGORIES = [
  '全部',
  '哈希表专题',
  '冲突处理策略',
  '负载因子优化',
  '分布式哈希',
  '习题集'
];

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeCourseId } = useCourse();
  const [searchTerm, setSearchTerm] = useState(location.state?.search ?? '');
  const [selectedCategory, setSelectedCategory] = useState(location.state?.category ?? '全部');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [allResources, setAllResources] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResources = async () => {
      if (!activeCourseId) return;
      try {
        setLoading(true);
        const res = await learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 20 });
        if (res.code === 200) {
          setAllResources(res.data.resources || []);
        }
      } catch (error) {
        console.error("Failed to fetch resources:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchResources();
  }, [activeCourseId]);

  // Filter logic
  const filteredResources = allResources.filter(resource => {
    const safeSearchTerm = (searchTerm || '').toLowerCase();
    const matchesSearch = resource.title.toLowerCase().includes(safeSearchTerm) ||
                          (resource.description && resource.description.toLowerCase().includes(safeSearchTerm));
    const matchesCategory = selectedCategory === '全部' || resource.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="min-h-screen bg-background text-on-background font-body-md antialiased overflow-x-hidden">
      {/* TopNavBar */}
      <Navbar searchTerm={searchTerm} onSearch={setSearchTerm} />

      {/* SideNavBar */}
      <aside className="h-full w-64 fixed left-0 top-16 bg-white border-r border-gray-100 flex flex-col py-6 space-y-2 font-['Public_Sans'] text-sm hidden md:flex">
        <div className="px-6 mb-6">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center text-white">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
            </div>
            <div>
              <h3 className="text-lg font-black text-cyan-600 leading-tight">数据结构掌控者</h3>
              <p className="text-[10px] text-gray-400 uppercase tracking-widest">多智能体学习系统</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1">
          <div className="px-4">
            <Link to="/learning-path" className="flex items-center space-x-3 px-4 py-3 rounded-lg text-gray-500 hover:bg-gray-50 transition-all duration-200 ease-in-out cursor-pointer hover:pl-5">
              <span className="material-symbols-outlined">account_tree</span>
              <span className="font-body-md">学习节点</span>
            </Link>
            <Link to="/dashboard" className="flex items-center space-x-3 px-4 py-3 rounded-lg bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500 transition-all duration-200 ease-in-out cursor-pointer hover:pl-5">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}>library_books</span>
              <span className="font-body-md">资源库</span>
            </Link>
          </div>
        </nav>
        <div className="px-6 mt-auto">
          <button className="w-full py-3 bg-primary-container text-on-primary-container rounded-xl font-bold active:scale-95 transition-all shadow-sm">
            启动新任务
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="pt-24 pb-12 md:pl-64 min-h-screen text-left">
        <div className="max-w-[1280px] mx-auto px-6 md:px-8">
          {/* Header Section */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-on-surface mb-2">资源库</h1>
            <p className="text-secondary text-sm">获取最新的哈希表与冲突解析学习资料、思维导图和实操代码。</p>
          </div>

          {/* Categories Filter */}
          <div className="flex flex-wrap gap-3 mb-8">
            {CATEGORIES.map(category => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={`px-5 py-2.5 rounded-full font-medium transition-all active:scale-95 ${
                  selectedCategory === category
                    ? 'bg-primary-container text-white shadow-md shadow-cyan-100'
                    : 'bg-white border border-outline-variant text-secondary hover:border-cyan-500 hover:text-cyan-600'
                }`}
              >
                {category === '全部' ? '全部专题' : category}
              </button>
            ))}
          </div>

          {/* Filter Feedback */}
          {(selectedCategory !== '全部' || searchTerm) && (
            <div className="mb-8 flex items-center gap-3 bg-surface-container-low p-4 rounded-xl border border-primary-container/30">
              <span className="material-symbols-outlined text-primary">filter_alt</span>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-on-surface-variant">当前筛选：</span>
                
                {selectedCategory !== '全部' && (
                  <span className="px-3 py-1 bg-primary text-white rounded-full text-xs font-medium flex items-center gap-1">
                    分类: {selectedCategory}
                    <button onClick={() => setSelectedCategory('全部')} className="hover:text-primary-container flex items-center justify-center cursor-pointer">
                      <span className="material-symbols-outlined text-[14px]">close</span>
                    </button>
                  </span>
                )}

                {searchTerm && (
                  <span className="px-3 py-1 bg-cyan-100 text-cyan-800 border border-cyan-200 rounded-full text-xs font-medium flex items-center gap-1">
                    关键词: "{searchTerm}"
                    <button onClick={() => setSearchTerm('')} className="hover:text-cyan-600 flex items-center justify-center cursor-pointer">
                      <span className="material-symbols-outlined text-[14px]">close</span>
                    </button>
                  </span>
                )}

                <button
                  onClick={() => { setSelectedCategory('全部'); setSearchTerm(''); }}
                  className="text-primary hover:underline text-xs flex items-center ml-2 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-xs mr-1">delete</span> 清除全部
                </button>
              </div>
            </div>
          )}

          {/* Two Column Grid Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
            {/* Left Column: Required Resources (8 columns) */}
            <div className="lg:col-span-8 space-y-gutter">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-on-surface flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>stars</span>
                  必修资源 (Required)
                </h2>
                <span className="text-xs text-secondary">
                  {loading ? '加载中...' : `${filteredResources.filter(r => r.type === 'Required').length} 个核心资源`}
                </span>
              </div>

              {/* Render Required Cards */}
              <div className="space-y-gutter">
                {loading ? (
                  <div className="py-12 flex justify-center"><span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span></div>
                ) : filteredResources.filter(r => r.type === 'Required').map(resource => {
                  // Featured Card with Image
                  if (resource.image) {
                    return (
                      <div key={resource.id} className="group relative overflow-hidden rounded-xl bg-white border border-outline-variant shadow-sm hover:shadow-xl hover:shadow-cyan-500/10 transition-all duration-300">
                        <div className="aspect-[21/9] w-full overflow-hidden">
                          <img
                            alt={resource.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                            src={resource.image}
                          />
                        </div>
                        <div className="p-6">
                          <div className="flex items-center gap-2 mb-3">
                            <span className="px-2 py-0.5 bg-primary text-white text-[10px] font-bold rounded flex items-center gap-1">
                              <span className="material-symbols-outlined text-[12px]" style={{ fontVariationSettings: "'FILL' 1" }}>bookmark</span> 必修
                            </span>
                            <span className="px-2 py-0.5 bg-cyan-100 text-cyan-700 text-[10px] font-bold rounded">{resource.badge}</span>
                            <span className="text-[10px] text-gray-400">{resource.duration}</span>
                          </div>
                          <h3 className="text-lg font-bold text-on-surface mb-2">{resource.title}</h3>
                          <p className="text-secondary text-sm mb-4 leading-relaxed">{resource.description}</p>
                          <div className="flex items-center justify-between">
                            <div className="flex -space-x-2">
                              {(resource.tags || []).map((tag, i) => (
                                <div key={i} className="w-8 h-8 rounded-full border-2 border-white bg-blue-100 flex items-center justify-center text-[10px] font-bold">
                                  {tag}
                                </div>
                              ))}
                            </div>
                            <button
                              onClick={() => navigate('/resource/detail')}
                              className="text-cyan-600 font-bold flex items-center gap-1 hover:gap-2 transition-all cursor-pointer"
                            >
                              开始学习 <span className="material-symbols-outlined text-sm">arrow_forward</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  // Code Practice Card
                  if (resource.codeCard) {
                    return (
                      <div key={resource.id} className="bg-slate-900 rounded-xl p-6 shadow-lg relative overflow-hidden group text-left">
                        <div className="absolute inset-0 opacity-10 pointer-events-none">
                          <svg fill="none" height="100%" width="100%" xmlns="http://www.w3.org/2000/svg">
                            <path d="M0 40H40V0M40 80H80V40M80 120H120V80" stroke="white" strokeWidth="0.5"></path>
                          </svg>
                        </div>
                        <div className="relative z-10 flex flex-col h-full">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 bg-primary text-white text-[10px] font-bold rounded">必修</span>
                              <div className={`w-10 h-10 ${resource.iconBg} rounded-lg flex items-center justify-center ${resource.iconColor}`}>
                                <span className="material-symbols-outlined">{resource.icon}</span>
                              </div>
                            </div>
                            <span className="text-cyan-400 font-mono text-xs">{resource.fileName}</span>
                          </div>
                          <span className="text-xs font-bold text-cyan-400/80 mb-2 block">代码实操</span>
                          <h3 className="text-lg font-bold text-white mb-2">{resource.title}</h3>
                          <p className="text-sm text-gray-400 mb-6 flex-1 leading-relaxed">{resource.description}</p>
                          <button
                            onClick={() => navigate('/quiz')}
                            className="w-full bg-cyan-400 text-slate-900 py-2.5 rounded-lg font-bold hover:bg-cyan-300 transition-colors cursor-pointer"
                          >
                            进入 IDE
                          </button>
                        </div>
                      </div>
                    );
                  }

                  // Standard Metric Card
                  return (
                    <div key={resource.id} className="bg-white rounded-xl border border-outline-variant p-6 shadow-sm hover:border-cyan-200 transition-colors">
                      <div className="flex items-center gap-3 mb-4">
                        <span className="px-2 py-0.5 bg-primary text-white text-[10px] font-bold rounded flex items-center gap-0.5">
                          <span className="material-symbols-outlined text-[10px]" style={{ fontVariationSettings: "'FILL' 1" }}>bookmark</span> 必修
                        </span>
                        <div className={`w-10 h-10 ${resource.iconBg} ${resource.iconColor} rounded-lg flex items-center justify-center`}>
                          <span className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}>{resource.icon}</span>
                        </div>
                        <span className="text-xs font-bold text-purple-600 uppercase tracking-tighter">{resource.subText}</span>
                      </div>
                      <h3 className="text-lg font-bold mb-2">{resource.title}</h3>
                      <p className="text-sm text-secondary mb-4 leading-relaxed">{resource.description}</p>
                      <div className="grid grid-cols-2 gap-2 mb-4">
                        {(resource.metrics || []).map((metric, i) => (
                          <div key={i} className="bg-surface-container rounded p-2 flex flex-col items-center">
                            <span className="text-cyan-600 font-bold text-sm">{metric.value}</span>
                            <span className="text-[10px] text-gray-500 uppercase">{metric.label}</span>
                          </div>
                        ))}
                      </div>
                      <button
                        onClick={() => navigate('/resource/detail')}
                        className="w-full border border-cyan-500 text-cyan-600 py-2 rounded-lg font-bold hover:bg-cyan-50 transition-colors cursor-pointer"
                      >
                        查看解析
                      </button>
                    </div>
                  );
                })}
                {!loading && filteredResources.filter(r => r.type === 'Required').length === 0 && (
                  <div className="text-center py-8 text-gray-400 text-sm">暂无匹配的必修资源</div>
                )}
              </div>
            </div>

            {/* Right Column: Elective/Recommended Resources (4 columns) */}
            <div className="lg:col-span-4 space-y-gutter">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-on-surface flex items-center gap-2">
                  <span className="material-symbols-outlined text-secondary">recommend</span>
                  推荐资源
                </h2>
              </div>

              {/* Render Recommended Cards */}
              <div className="space-y-gutter">
                {loading ? (
                  <div className="py-12 flex justify-center"><span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span></div>
                ) : filteredResources.filter(r => r.type === 'Recommended').map(resource => {
                  // Book Card
                  if (resource.bookCard) {
                    return (
                      <div key={resource.id} className="bg-white rounded-xl border border-outline-variant p-6 shadow-sm hover:border-cyan-200 transition-colors">
                        <div className="flex items-center gap-4 mb-4">
                          <div className="w-16 h-20 bg-gray-100 rounded overflow-hidden flex-shrink-0">
                            <img alt={resource.title} className="w-full h-full object-cover" src={resource.image} />
                          </div>
                          <div>
                            <span className="text-xs font-bold text-secondary mb-1 block">拓展阅读</span>
                            <h3 className="text-base font-bold leading-tight">{resource.title}</h3>
                            <p className="text-xs text-gray-400 mt-1">作者: {resource.author}</p>
                          </div>
                        </div>
                        <p className="text-sm text-secondary mb-4 leading-relaxed line-clamp-3">{resource.description}</p>
                      </div>
                    );
                  }

                  // Exercise Card
                  if (resource.meta) {
                    return (
                      <div key={resource.id} className="bg-white rounded-xl border border-outline-variant p-6 shadow-sm hover:border-cyan-200 transition-colors">
                        <div className="flex items-start justify-between mb-4">
                          <div className={`w-12 h-12 ${resource.iconBg} rounded-lg flex items-center justify-center ${resource.iconColor}`}>
                            <span className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}>{resource.icon}</span>
                          </div>
                          <span className="px-2 py-1 bg-green-50 text-green-700 text-[10px] font-bold rounded">推荐练习</span>
                        </div>
                        <span className="text-xs font-bold text-orange-500 mb-2 block">{resource.subText}</span>
                        <h3 className="text-lg font-bold mb-2">{resource.title}</h3>
                        <p className="text-sm text-secondary mb-4 leading-relaxed">{resource.description}</p>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          {(resource.meta || []).map((meta, i) => (
                            <span key={i} className="flex items-center gap-1">
                              <span className="material-symbols-outlined text-sm">{meta.icon}</span> {meta.text}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  }

                  // Standard Recommended Card (e.g. Mind Map)
                  return (
                    <div key={resource.id} className="bg-white rounded-xl border border-outline-variant p-6 shadow-sm flex flex-col hover:border-cyan-200 transition-colors">
                      <div className={`w-12 h-12 ${resource.iconBg} rounded-lg flex items-center justify-center ${resource.iconColor} mb-4`}>
                        <span className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}>{resource.icon}</span>
                      </div>
                      <div className="flex-1">
                        <span className="text-xs font-bold text-cyan-600 mb-2 block">{resource.subText}</span>
                        <h3 className="text-lg font-bold mb-2">{resource.title}</h3>
                        <p className="text-sm text-secondary mb-4 leading-relaxed">{resource.description}</p>
                      </div>
                      <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                        <span className="text-xs text-gray-400">{resource.footer}</span>
                        {resource.downloadable && (
                          <button className="p-2 hover:bg-gray-50 rounded-full transition-colors cursor-pointer">
                            <span className="material-symbols-outlined text-gray-400">download</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
                {!loading && filteredResources.filter(r => r.type === 'Recommended').length === 0 && (
                  <div className="text-center py-8 text-gray-400 text-sm">暂无匹配的推荐资源</div>
                )}
              </div>
            </div>
          </div>

          {/* Load More */}
          <div className="mt-12 flex flex-col items-center gap-4">
            <button className="px-8 py-3 bg-white border border-outline-variant rounded-full text-secondary font-medium hover:bg-gray-50 transition-all active:scale-95 shadow-sm cursor-pointer">
              加载更多哈希表资源
            </button>
            <p className="text-xs text-gray-400">已显示 {filteredResources.length} / 42 个专题资源</p>
          </div>
        </div>
      </main>

      {/* Contextual FAB */}
      <button
        onClick={() => navigate('/ai-chat')}
        className="fixed bottom-8 right-8 w-14 h-14 bg-cyan-500 text-white rounded-full shadow-2xl shadow-cyan-500/40 flex items-center justify-center hover:scale-110 active:scale-90 transition-all z-40 cursor-pointer"
      >
        <span className="material-symbols-outlined text-2xl">chat_bubble</span>
      </button>

      {/* Study Report Modal */}
      <TrainingReportModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </div>
  );
}
