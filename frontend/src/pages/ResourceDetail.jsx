
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { learningService } from '../api/services/learning';

export default function ResourceDetail() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      learningService.getResourceDetail(id).then(res => {
        if (res.code === 200) setResource(res.data);
      }).catch(() => setResource(null))
      .finally(() => setLoading(false));
    }
  }, [id]);

  if (loading) {
    return (
      <div className="bg-background text-on-background font-body-md min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-outline">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-background text-on-background font-body-md min-h-screen">
      {/* Top Navigation Bar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-gray-100 shadow-sm font-['Public_Sans']">
        <div className="flex items-center justify-between px-6 h-16 max-w-[1280px] mx-auto">
          <div className="text-xl font-bold tracking-tight text-cyan-600">数据结构智能助手</div>
          <div className="hidden md:flex items-center space-x-8">
            <Link to="/profile" className="text-gray-600 hover:text-cyan-500 transition-colors">个人信息</Link>
            <Link to="/learning-path" className="text-gray-600 hover:text-cyan-500 transition-colors">路径规划</Link>
            <Link to="/dashboard" className="text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1">资源库</Link>
            <Link to="/ai-chat" className="text-gray-600 hover:text-cyan-500 transition-colors">AI答疑</Link>
            <Link to="/learning-effects" className="text-gray-600 hover:text-cyan-500 transition-colors">学习效果</Link>
          </div>
          <div className="flex items-center space-x-4">
            <button className="p-2 hover:bg-gray-50 rounded-lg transition-all active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-gray-600">notifications</span>
            </button>
            <button className="w-8 h-8 rounded-full overflow-hidden border border-gray-200 cursor-pointer">
              <img src="https://lh3.googleusercontent.com/aida-public/AB6AXuBD7zzVzJP4sOCCImNhQnVh0f5VXBKYUUdqITWBaQkw7NykTFWpBCRb35x5OdjOfAeHA8pxnY1dbeHj7om4AmK_nGXsoIN-1mbwE3hCNq7xFNt4SuldmZvdW3PqPIvYRwW_EBGaXqZId-3waaJh8IQcMRBeypeQMRJI5hJFBhbeybYWhNhoWkUKSfTBuQqCIzu6dKwDMXS9LUFS_FZN0utek2XOAcc_3gZ3uXN6djZJ4T2_TfvwsvZ-1jgokz1Htpu6VTO_yqFDEOvS" alt="Profile" />
            </button>
          </div>
        </div>
      </nav>

      {/* Sidebar */}
      <aside className="h-full w-64 fixed left-0 bg-white border-r border-gray-100 font-['Public_Sans'] text-sm hidden lg:block top-16 z-10 pt-6 pb-24 overflow-y-auto">
        <div className="flex flex-col px-4 space-y-6">
          {/* Back Button */}
          <button 
            onClick={() => navigate(-1)}
            className="flex items-center gap-3 px-4 py-3 rounded-xl border border-outline-variant text-on-surface-variant hover:bg-surface-container-low transition-all"
          >
            <span className="material-symbols-outlined">arrow_back</span>
            <span className="font-semibold">返回资源列表</span>
          </button>
          
          <div className="space-y-2">
            <div className="flex items-center p-3 rounded-lg text-gray-500 hover:bg-gray-50 transition-all cursor-pointer hover:pl-2">
              <span className="material-symbols-outlined mr-3">account_tree</span>
              学习节点
            </div>
            <div className="flex items-center p-3 rounded-lg bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500 transition-all cursor-pointer hover:pl-2">
              <span className="material-symbols-outlined mr-3">library_books</span>
              资源库
            </div>
          </div>

          {/* Keywords */}
          <div className="space-y-2">
            <h4 className="text-label-sm text-outline uppercase font-bold px-2">核心关键词</h4>
            <div className="flex flex-wrap gap-2 px-2">
              {resource?.tags?.map((tag, idx) => (
                <span key={idx} className="px-2 py-1 bg-surface-container-high text-on-surface-variant rounded text-xs border border-outline-variant">{tag}</span>
              ))}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Canvas */}
      <main className="ml-0 lg:ml-64 min-h-screen pt-16">
        <div className="max-w-[960px] mx-auto px-6 py-10">

          {/* Document Display Section */}
          <article className="bg-white p-10 rounded-xl shadow-[0px_4px_20px_rgba(0,0,0,0.04)] border border-outline-variant hover:shadow-lg transition-shadow duration-300">
              <header className="mb-8 border-b border-surface-container-highest pb-6">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="px-3 py-1 bg-cyan-100 text-cyan-800 rounded-full text-xs font-bold">深度解析</span>
                  {resource?.chapter && <span className="px-3 py-1 bg-surface-container-high text-on-surface-variant rounded-full text-xs">章节: {resource.chapter}</span>}
                  {resource?.knowledge_point && <span className="px-3 py-1 bg-surface-container-high text-on-surface-variant rounded-full text-xs">知识点: {resource.knowledge_point}</span>}
                </div>
                <h1 className="text-h1 font-h1 text-on-surface mb-4">{resource?.title || '加载中...'}</h1>
                <p className="text-body-lg text-on-surface-variant leading-relaxed">
                  {resource?.description || ''}
                </p>
              </header>

              <section className="prose prose-slate max-w-none text-on-surface-variant">
                <p className="text-body-md whitespace-pre-wrap">
                  {resource?.content_preview || '暂无正文预览'}
                </p>
              </section>

              <footer className="mt-12 pt-8 border-t border-surface-container-highest flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <button className="flex items-center gap-2 text-outline hover:text-primary transition-colors cursor-pointer">
                    <span className="material-symbols-outlined">thumb_up</span>
                    <span className="text-label-sm">有用</span>
                  </button>
                  <button className="flex items-center gap-2 text-outline hover:text-primary transition-colors cursor-pointer">
                    <span className="material-symbols-outlined">share</span>
                    <span className="text-label-sm">分享</span>
                  </button>
                </div>
                <div className="flex gap-4">
                  <button className="px-6 py-2 rounded-lg border border-primary text-primary font-semibold hover:bg-primary-container/10 transition-all active:scale-95 cursor-pointer">
                    收藏笔记
                  </button>
                  <button className="px-8 py-2 rounded-lg bg-primary-container text-on-primary-container font-bold shadow-lg shadow-primary-container/20 hover:brightness-105 transition-all active:scale-95 cursor-pointer">
                    下一章节
                  </button>
                </div>
              </footer>
          </article>

        </div>
      </main>
    </div>
  );
}
