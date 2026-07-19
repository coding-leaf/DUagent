import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useResourceDetail } from '../hooks/useResourceDetail';
import { useResourceStudyTracking } from '../hooks/useResourceStudyTracking';
import { useCourse } from '../context/CourseContext';
import Icon from '../components/Icon';
import MarkdownViewer from '../components/common/MarkdownViewer';

const TYPE_LABELS = {
  lesson: '标准讲义',
  diagram: '知识图解',
  example: '代码示例',
  document: '文档',
  reading: '阅读材料',
  code: '代码示例',
  mindmap: '思维导图',
  video: '视频',
};

const getDisplayContent = (resource) => {
  if (!resource) return '';
  return resource.content || resource.content_preview || '';
};

// 工具函数：美化标签 (清理诸如 kg_node:xx 之类的开发用语)
const formatTag = (tag) => {
  if (!tag) return '';
  if (tag.startsWith('kg_node:')) return tag.replace('kg_node:', '知识节点: ');
  if (tag.startsWith('support_band:')) return ''; // 直接忽略
  return tag;
};

export default function ResourceDetail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams();
  const { activeCourseId } = useCourse();
  const { resource, loading } = useResourceDetail(id);
  const nodeContext = location.state?.node || {};
  useResourceStudyTracking({
    courseId: activeCourseId || resource?.course_id,
    resource,
    nodeContext
  });

  if (loading) {
    return (
      <div className="bg-slate-50 min-h-screen flex items-center justify-center font-['Plus_Jakarta_Sans',sans-serif]">
        <div className="text-center">
          <div className="animate-spin w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-slate-500 font-medium tracking-wide">加载资源详情中...</p>
        </div>
      </div>
    );
  }

  if (!resource) {
    return (
      <div className="bg-slate-50 min-h-screen flex items-center justify-center font-['Plus_Jakarta_Sans',sans-serif]">
        <div className="text-center">
          <Icon name="sentiment_dissatisfied" className="material-symbols-outlined text-slate-300 text-6xl mb-4"/>
          <p className="text-slate-500 font-medium mb-6">未找到该资源或获取失败</p>
          <button onClick={() => navigate(-1)} className="px-6 py-2 bg-cyan-600 text-white rounded-full font-semibold hover:bg-cyan-700 transition-colors">
            返回上一页
          </button>
        </div>
      </div>
    );
  }

  // 清洗展示标签
  const displayTags = (resource.tags || []).map(formatTag).filter(Boolean);

  let finalContent = getDisplayContent(resource) || '';
  if (['diagram', 'mindmap'].includes(resource.type) && !/^```/m.test(finalContent)) {
    finalContent = `\`\`\`mermaid\n${finalContent}\n\`\`\``;
  } else if (['example', 'code'].includes(resource.type) && !finalContent.includes('```') && !/^#+\s/m.test(finalContent)) {
    finalContent = `\`\`\`\n${finalContent}\n\`\`\``; 
  }

  return (
    <div className="bg-slate-50 text-slate-800 font-['Plus_Jakarta_Sans',sans-serif] min-h-screen relative selection:bg-cyan-200 selection:text-cyan-900">
      
      {/* Top Floating Navigation */}
      <nav className="sticky top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/60 shadow-sm transition-all duration-300">
        <div className="flex items-center justify-between px-4 lg:px-8 h-16 max-w-[1280px] mx-auto">
          <button 
            onClick={() => navigate(-1)}
            className="group flex items-center gap-2 px-4 py-2 rounded-full hover:bg-slate-100 transition-all text-slate-600 hover:text-cyan-700"
          >
            <Icon name="arrow_back" className="material-symbols-outlined text-lg transition-transform group-hover:-translate-x-1"/>
            <span className="font-bold text-sm">返回</span>
          </button>
          <div className="text-sm font-bold text-slate-400 uppercase tracking-widest hidden sm:block">EduAgent • Resource Viewer</div>
          <div className="w-24"></div> {/* Balance spacer */}
        </div>
      </nav>

      {/* Main Content Canvas */}
      <main className="min-h-screen pt-12 pb-24">
        <div className="max-w-[800px] mx-auto px-4 sm:px-6">

          {/* Document Display Section */}
          <article className="bg-white px-6 py-10 sm:p-12 lg:p-16 rounded-[2rem] shadow-sm border border-slate-200/60 hover:shadow-md transition-shadow duration-300">
              <header className="mb-10 pb-8 border-b border-slate-100">
                <div className="flex items-center gap-2 mb-6 flex-wrap">
                  <span className="px-3.5 py-1.5 bg-cyan-100 text-cyan-800 rounded-full text-xs font-bold tracking-wide flex items-center gap-1.5">
                    <Icon name="auto_awesome" className="material-symbols-outlined text-[14px]"/>
                    {TYPE_LABELS[resource.type] || '学习资源'}
                  </span>
                  {resource.chapter && (
                    <span className="px-3.5 py-1.5 bg-slate-100 text-slate-600 rounded-full text-xs font-bold tracking-wide">
                      章节: {resource.chapter}
                    </span>
                  )}
                  {resource.knowledge_point && (
                    <span className="px-3.5 py-1.5 bg-slate-100 text-slate-600 rounded-full text-xs font-bold tracking-wide">
                      知识点: {resource.knowledge_point}
                    </span>
                  )}
                </div>
                
                <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 leading-tight mb-6 tracking-tight">
                  {resource.title}
                </h1>
                
                {resource.description && (
                  <p className="text-lg text-slate-500 leading-relaxed font-medium">
                    {resource.description}
                  </p>
                )}
              </header>

              <section className="max-w-none">
                {finalContent ? (
                  <MarkdownViewer content={finalContent} className="text-[15px] text-slate-700" />
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200">
                    <Icon name="do_not_disturb_off" className="material-symbols-outlined text-slate-300 text-5xl mb-4"/>
                    <p className="text-slate-500 font-medium">暂无内容数据</p>
                  </div>
                )}
              </section>

              {/* Tags Section */}
              {displayTags.length > 0 && (
                <div className="mt-12 pt-8 border-t border-slate-100">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">相关标签</h4>
                  <div className="flex flex-wrap gap-2">
                    {displayTags.map((tag, idx) => (
                      <span key={idx} className="px-3 py-1.5 bg-slate-50 text-slate-500 rounded-lg text-xs font-medium border border-slate-200/60 hover:bg-slate-100 transition-colors cursor-default">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

          </article>

        </div>
      </main>
    </div>
  );
}
