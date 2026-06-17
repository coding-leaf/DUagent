import Icon from '../Icon';
import FeedbackStatus from '../FeedbackStatus';

const resourceTypeLabels = {
  document: '文档',
  reading: '阅读材料',
  code: '代码示例',
  mindmap: '思维导图',
  video: '视频',
};

export default function TeacherResourceSection({
  activeClassInfo,
  resourcesLoading,
  resourcesError,
  resources,
  groupedResources,
  expandedChapter,
  setExpandedChapter,
  handleCopyCourseCode,
  copiedCourseCode,
  navigate
}) {
  return (
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
  );
}
