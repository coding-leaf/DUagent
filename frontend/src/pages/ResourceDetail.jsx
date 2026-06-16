import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import { learningService } from '../api/services/learning';
import { learningActivityService } from '../api/services/learningActivity';
import Icon from '../components/Icon';

const TYPE_LABELS = {
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

const normalizeMermaidSource = (content) => {
  const trimmed = (content || '').trim();
  const fenced = trimmed.match(/^```(?:mermaid)?\s*([\s\S]*?)```$/i);
  return fenced ? fenced[1].trim() : trimmed;
};

// 工具函数：美化标签 (清理诸如 kg_node:xx 之类的开发用语)
const formatTag = (tag) => {
  if (!tag) return '';
  if (tag.startsWith('kg_node:')) return tag.replace('kg_node:', '知识节点: ');
  if (tag.startsWith('support_band:')) return ''; // 直接忽略
  return tag;
};

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'strict',
  theme: 'default',
});

function MermaidDiagram({ content }) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const source = normalizeMermaidSource(content);

  useEffect(() => {
    let cancelled = false;

    const renderDiagram = async () => {
      if (!source) {
        setSvg('');
        setError('');
        return;
      }

      let renderId = '';
      try {
        renderId = `resource-mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const result = await mermaid.render(renderId, source);
        if (result.svg.includes('error in text')) {
          throw new Error('Mermaid syntax error');
        }
        if (!cancelled) {
          setSvg(result.svg);
          setError('');
        }
      } catch (err) {
        console.error('Mermaid render failed:', err);
        if (!cancelled) {
          setSvg('');
          setError('思维导图渲染失败，已显示原始内容。');
        }
      } finally {
        if (renderId) {
          document.getElementById(renderId)?.remove();
          document.getElementById(`d${renderId}`)?.remove();
        }
      }
    };

    renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [source]);

  return (
    <div className="rounded-2xl border border-cyan-100 bg-cyan-50/30 p-6 my-8">
      <div className="mb-4 flex items-center gap-2 text-cyan-700">
        <Icon name="schema" className="material-symbols-outlined text-xl"/>
        <span className="text-base font-bold">思维导图解析</span>
      </div>
      {svg ? (
        <div
          className="overflow-x-auto rounded-xl bg-white p-6 shadow-sm [&_svg]:mx-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ) : (
        <p className="text-body-md whitespace-pre-wrap text-slate-700">{source}</p>
      )}
      {error && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </div>
      )}
    </div>
  );
}

export default function ResourceDetail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams();
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);
  const studyStartRef = useRef(null);
  const trackingResourceRef = useRef(null);
  const nodeContext = location.state?.node || {};

  useEffect(() => {
    if (id) {
      learningService.getResourceDetail(id).then(res => {
        if (res.code === 200) setResource(res.data);
      }).catch(() => setResource(null))
      .finally(() => setLoading(false));
    }
  }, [id]);

  useEffect(() => {
    if (!resource?.id || !resource?.course_id) return undefined;

    const activityContext = {
      course_id: resource.course_id,
      resource_id: resource.id,
      node_id: nodeContext.id || nodeContext.node_id || null,
      node_name: nodeContext.name || nodeContext.node_name || resource.knowledge_point || null
    };

    studyStartRef.current = Date.now();
    trackingResourceRef.current = activityContext;
    learningActivityService.trackActivity({
      ...activityContext,
      activity_type: 'resource_view',
      metadata: { source: 'resource_detail' }
    });

    return () => {
      const startedAt = studyStartRef.current;
      const trackedResource = trackingResourceRef.current;
      if (!startedAt || !trackedResource) return;
      const duration = Math.floor((Date.now() - startedAt) / 1000);
      if (duration < learningActivityService.minStudySeconds) return;
      learningActivityService.trackActivity({
        ...trackedResource,
        activity_type: 'resource_study',
        duration_seconds: duration,
        metadata: { source: 'resource_detail' }
      });
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource]);

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

              <section className="prose prose-slate prose-lg max-w-none text-slate-700 marker:text-cyan-500 prose-headings:text-slate-800 prose-a:text-cyan-600 hover:prose-a:text-cyan-700">
                {getDisplayContent(resource) ? (
                  resource.type === 'code' ? (
                    <div className="relative group">
                      <pre className="rounded-2xl bg-slate-900 p-6 text-sm text-slate-50 overflow-x-auto shadow-inner border border-slate-800 font-mono">
                        <code>{getDisplayContent(resource)}</code>
                      </pre>
                    </div>
                  ) : resource.type === 'mindmap' ? (
                    <MermaidDiagram content={getDisplayContent(resource)} />
                  ) : (
                    <div className="whitespace-pre-wrap leading-relaxed">
                      {getDisplayContent(resource)}
                    </div>
                  )
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200">
                    <Icon name="do_not_disturb_off" className="material-symbols-outlined text-slate-300 text-5xl mb-4"/>
                    <p className="text-slate-500 font-medium">
                      暂无内容数据
                    </p>
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

              <footer className="mt-8 pt-8 flex justify-center items-center gap-6">
                <button className="group flex items-center justify-center gap-2 w-32 h-12 rounded-full border border-slate-200 text-slate-600 hover:bg-cyan-50 hover:text-cyan-600 hover:border-cyan-200 transition-all font-bold text-sm">
                  <Icon name="thumb_up" className="material-symbols-outlined text-[20px] transition-transform group-hover:-translate-y-1"/>
                  <span>有用</span>
                </button>
                <button className="group flex items-center justify-center gap-2 w-32 h-12 rounded-full border border-slate-200 text-slate-600 hover:bg-cyan-50 hover:text-cyan-600 hover:border-cyan-200 transition-all font-bold text-sm">
                  <Icon name="share" className="material-symbols-outlined text-[20px] transition-transform group-hover:rotate-12"/>
                  <span>分享</span>
                </button>
              </footer>
          </article>

        </div>
      </main>
    </div>
  );
}
