import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { learningService } from '../api/services/learning';
import { learningActivityService } from '../api/services/learningActivity';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
import Icon from '../components/Icon';

export default function LearningPath() {
  const { activeCourseId } = useCourse();
  const [learningPath, setLearningPath] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [nodeResources, setNodeResources] = useState(null);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [showFullExercises, setShowFullExercises] = useState(false);
  const [showAllTutorials, setShowAllTutorials] = useState(false);
  const [showAllExercises, setShowAllExercises] = useState(false);
  const [showAllMaterials, setShowAllMaterials] = useState(false);
  const initialSelectionSkippedRef = useRef(false);

  useEffect(() => {
    const fetchPath = async () => {
      if (!activeCourseId) return;
      try {
        setLoading(true);
        const res = await learningService.getLearningPath(activeCourseId);
        if (res.code === 200) {
          setLearningPath(res.data);
        }
      } catch (error) {
        console.error("Failed to fetch learning path:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchPath();
  }, [activeCourseId]);

  const fetchNodeResources = useCallback(async (nodeId) => {
    if (!nodeId || !activeCourseId) return;
    try {
      setResourcesLoading(true);
      const res = await learningService.getNodeResources(nodeId, activeCourseId);
      if (res.code === 200) {
        setNodeResources(res.data);
      }
    } catch (error) {
      console.error("Failed to fetch node resources:", error);
      setNodeResources(null);
    } finally {
      setResourcesLoading(false);
    }
  }, [activeCourseId]);

  // Default selected node (after learningPath loads)
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!learningPath?.nodes?.length) return;
    const cpId = learningPath.current_position?.node_id;
    if (cpId) { setSelectedNodeId(cpId); return; }
    const ip = learningPath.nodes.find(n => n.status === 'in_progress');
    if (ip) { setSelectedNodeId(ip.id); return; }
    const rec = learningPath.nodes.find(n => n.status === 'recommended');
    if (rec) { setSelectedNodeId(rec.id); return; }
    const first = learningPath.nodes.find(n => n.status !== 'pending');
    if (first) { setSelectedNodeId(first.id); return; }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [learningPath]);

  // Fetch resources when selectedNodeId changes
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (selectedNodeId) {
      fetchNodeResources(selectedNodeId);
      setShowFullExercises(false);
      setShowAllTutorials(false);
      setShowAllExercises(false);
      setShowAllMaterials(false);
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [selectedNodeId, fetchNodeResources]);

  useEffect(() => {
    if (!activeCourseId || !selectedNodeId || !learningPath?.nodes?.length) return;
    const selectedNode = learningPath.nodes.find((node) => node.id === selectedNodeId);
    if (!selectedNode) return;
    if (!initialSelectionSkippedRef.current) {
      initialSelectionSkippedRef.current = true;
      return;
    }
    learningActivityService.trackActivity({
      course_id: activeCourseId,
      activity_type: 'node_view',
      node_id: selectedNode.id,
      node_name: selectedNode.name,
      metadata: { source: 'learning_path' }
    });
  }, [activeCourseId, learningPath, selectedNodeId]);

  const scrollContainerRef = useRef(null);

  // Convert vertical mouse wheel scroll to horizontal scroll for the learning path nodes
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      // Only intercept if it's primarily a vertical scroll
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        // Multiply deltaY to make it feel less heavy/exhausting
        const speedMultiplier = 2.5; 
        container.scrollLeft += e.deltaY * speedMultiplier;
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, [loading]);

  return (
    <div className="font-body-md bg-background min-h-screen text-on-background">
      {/* TopNavBar Implementation */}
      <Navbar />

      {/* Main Content Canvas */}
      <main className="pt-16 min-h-screen">
        <div className="max-w-[1280px] mx-auto p-gutter space-y-md">
          {/* Header Section */}
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-md mb-sm">
            <div>
              <h1 className="font-h1 text-h1 text-on-background">学习路径规划</h1>
            </div>

          </header>

          {/* Learning Path Visualizer */}
          <section className="bg-surface-container-lowest border border-gray-100 rounded-xl p-md shadow-sm overflow-hidden">
            <div className="flex items-center justify-between mb-lg">
              <h3 className="font-h3 text-h3 flex items-center space-x-sm">
                <Icon name="insights" className="material-symbols-outlined text-cyan-600"/>
                <span>闯关节点规划</span>
              </h3>
              <div className="flex space-x-base">
                <div className="flex items-center text-label-sm text-gray-400">
                  <span className="w-3 h-3 rounded-full bg-cyan-500 mr-xs"></span> 已完成
                </div>
                <div className="flex items-center text-label-sm text-gray-400">
                  <span className="w-3 h-3 rounded-full bg-surface-container-highest mr-xs"></span> 进行中
                </div>
              </div>
            </div>

            {/* Horizontal Scrolling Path */}
            <div ref={scrollContainerRef} className="relative flex items-center py-xl overflow-x-auto no-scrollbar min-h-[300px]">
              {loading ? (
                <div className="w-full flex justify-center"><Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-cyan-500"/></div>
              ) : (
                <>
                  {/* Path Line - Clean Minimal Line */}
                  <div className="absolute top-1/2 left-0 w-full h-[2px] bg-slate-200 -translate-y-1/2 z-0"></div>

                  {learningPath?.nodes.map((node) => {
                    if (node.status === 'completed') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-emerald-500 ring-offset-2 rounded-xl' : ''}`}>
                          <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3 border border-emerald-100 transition-colors group-hover:bg-emerald-100">
                            <Icon name="check" className="text-xl"/>
                          </div>
                          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm w-full transition-all duration-200 group-hover:shadow-md">
                            <span className="text-[11px] font-semibold text-emerald-600 tracking-wider mb-1 block">阶段 {node.order}</span>
                            <p className="text-base font-medium text-slate-800 mb-4">{node.name}</p>
                            <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                              <div className="h-full bg-emerald-500 w-full"></div>
                            </div>
                          </div>
                        </div>
                      );
                    } else if (node.status === 'in_progress') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-blue-500 ring-offset-2 rounded-xl' : ''}`}>
                          <div className="w-10 h-10 rounded-lg bg-blue-600 text-white flex items-center justify-center mb-3 shadow-md">
                            <Icon name="play_arrow" className="text-xl"/>
                          </div>
                          <div className="bg-white p-5 rounded-xl border border-blue-600 shadow-md w-full relative transition-all duration-200 group-hover:shadow-lg">
                            <div className="absolute -top-2.5 left-5 bg-blue-600 text-white text-[10px] font-bold tracking-wide px-2 py-0.5 rounded shadow-sm">进行中</div>
                            <span className="text-[11px] font-semibold text-blue-600 tracking-wider mb-1 block">阶段 {node.order}</span>
                            <p className="text-base font-medium text-slate-900 mb-4">{node.name}</p>
                            <div className="space-y-1.5">
                              <div className="flex justify-between text-[11px] font-medium text-slate-500">
                                <span>当前进度</span>
                                <span>{node.mastery}%</span>
                              </div>
                              <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-600 transition-all duration-500" style={{ width: `${node.mastery}%` }}></div>
                              </div>
                            </div>
                            <div className="mt-4">
                              <Link to="/dashboard" state={{ search: node.name }} className="w-full py-1.5 bg-slate-50 hover:bg-slate-100 text-blue-700 rounded-lg text-sm font-medium flex items-center justify-center gap-1.5 transition-colors border border-slate-200">
                                <Icon name="auto_stories" className="text-sm"/> 继续学习
                              </Link>
                            </div>
                          </div>
                        </div>
                      );
                    } else if (node.status === 'recommended') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-indigo-400 ring-offset-2 rounded-xl' : ''}`}>
                          <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 border border-indigo-100 transition-colors group-hover:bg-indigo-100">
                            <Icon name="auto_awesome" className="text-xl"/>
                          </div>
                          <div className="bg-white p-5 rounded-xl border border-indigo-200 shadow-sm w-full transition-all duration-200 group-hover:shadow-md">
                            <span className="text-[11px] font-semibold text-indigo-600 tracking-wider mb-1 block">阶段 {node.order}</span>
                            <p className="text-base font-medium text-slate-800 mb-4">{node.name}</p>
                            <div className="h-1.5 w-full bg-indigo-50 rounded-full overflow-hidden mb-3">
                              <div className="h-full bg-indigo-300 w-0"></div>
                            </div>
                            <div className="text-[11px] font-medium text-indigo-500 flex items-center gap-1">
                              <Icon name="info" className="text-[14px]"/> 推荐预习
                            </div>
                          </div>
                        </div>
                      );
                    } else {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 px-4 flex flex-col items-center group w-72 cursor-pointer opacity-80 hover:opacity-100 transition-opacity ${node.id === selectedNodeId ? 'ring-2 ring-slate-300 ring-offset-2 rounded-xl' : ''}`}>
                          <div className="w-10 h-10 rounded-lg bg-slate-100 text-slate-400 flex items-center justify-center mb-3 transition-colors group-hover:bg-slate-200 group-hover:text-slate-500">
                            <Icon name="explore" className="text-xl"/>
                          </div>
                          <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 w-full transition-all duration-200 group-hover:border-slate-300">
                            <span className="text-[11px] font-semibold text-slate-400 tracking-wider mb-1 block transition-colors group-hover:text-slate-500">阶段 {node.order}</span>
                            <p className="text-base font-medium text-slate-500 mb-4 transition-colors group-hover:text-slate-700">{node.name}</p>
                            <div className="h-1 w-full bg-slate-200 rounded-full"></div>
                            <div className="mt-3 text-[11px] font-medium text-slate-400 flex items-center gap-1 transition-colors group-hover:text-slate-500">
                              <Icon name="arrow_forward" className="text-[14px]"/> 尚未学习
                            </div>
                          </div>
                        </div>
                      );
                    }
                  })}
                </>
              )}
            </div>
          </section>

          {/* Node Resources Panel */}
          {selectedNodeId && (
            <section className="mt-8 space-y-6">
              <h3 className="font-h3 text-h3 flex items-center gap-2">
                <Icon name="library_books" className="material-symbols-outlined text-cyan-600"/>
                当前节点资源
                {nodeResources?.node_name && (
                  <span className="text-body-md text-secondary font-normal">— {nodeResources.node_name}</span>
                )}
              </h3>

              {resourcesLoading ? (
                <div className="flex justify-center py-12">
                  <Icon name="progress_activity" className="material-symbols-outlined animate-spin text-4xl text-cyan-500"/>
                </div>
              ) : nodeResources ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* 1. 薄弱点讲解 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-orange-50 rounded-lg text-orange-600">
                        <Icon name="lightbulb" className="material-symbols-outlined"/>
                      </div>
                      <h4 className="font-bold text-on-surface">薄弱点讲解</h4>
                    </div>
                    {nodeResources.weak_point_tutorials?.length > 0 ? (
                      <div className="space-y-3 max-h-80 overflow-y-auto">
                        {(showAllTutorials ? nodeResources.weak_point_tutorials : nodeResources.weak_point_tutorials.slice(0, 5)).map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <p className="text-sm font-bold text-on-surface mb-1">{item.title}</p>
                            <p className="text-xs text-secondary line-clamp-2 mb-2">{item.content || ''}</p>
                            {item.id ? (
                              <Link to={`/resource/${item.id}`} state={{ node: { id: selectedNodeId, name: nodeResources.node_name } }} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1">
                                查看资源 <Icon name="arrow_forward" className="material-symbols-outlined text-xs"/>
                              </Link>
                            ) : (
                              <span className="text-xs text-gray-400">暂无详情</span>
                            )}
                          </div>
                        ))}
                        {nodeResources.weak_point_tutorials.length > 5 && (
                          <button onClick={() => setShowAllTutorials(!showAllTutorials)}
                            className="text-xs text-cyan-600 hover:text-cyan-700 font-medium w-full text-center py-1">
                            {showAllTutorials ? '收起' : `展开全部 (${nodeResources.weak_point_tutorials.length} 条)`}
                          </button>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无薄弱点讲解</p>
                    )}
                  </div>

                  {/* 2. 节点练习 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                        <Icon name="quiz" className="material-symbols-outlined"/>
                      </div>
                      <h4 className="font-bold text-on-surface">节点练习</h4>
                    </div>
                    {nodeResources.exercises?.length > 0 ? (
                      <div className="space-y-3 max-h-80 overflow-y-auto">
                        {(showAllExercises ? nodeResources.exercises : nodeResources.exercises.slice(0, 5)).map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[10px] rounded font-bold">
                                {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                              </span>
                            </div>
                            <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                          </div>
                        ))}
                        {nodeResources.exercises.length > 5 && (
                          <button onClick={() => setShowAllExercises(!showAllExercises)}
                            className="text-xs text-cyan-600 hover:text-cyan-700 font-medium w-full text-center py-1">
                            {showAllExercises ? '收起' : `展开全部 (${nodeResources.exercises.length} 条)`}
                          </button>
                        )}
                        <Link to={`/quiz?course_id=${activeCourseId}&node_id=${selectedNodeId}`} className="w-full block text-center py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors">
                          进入练习
                        </Link>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无练习</p>
                    )}
                  </div>

                  {/* 3. 章节资料 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-emerald-50 rounded-lg text-emerald-600">
                        <Icon name="menu_book" className="material-symbols-outlined"/>
                      </div>
                      <h4 className="font-bold text-on-surface">章节资料</h4>
                    </div>
                    {nodeResources.chapter_materials?.length > 0 ? (
                      <div className="space-y-3 max-h-80 overflow-y-auto">
                        {(showAllMaterials ? nodeResources.chapter_materials : nodeResources.chapter_materials.slice(0, 5)).map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] rounded font-bold">
                                {item.type || '资料'}
                              </span>
                              <p className="text-sm font-bold text-on-surface">{item.title}</p>
                            </div>
                            {item.id ? (
                              <Link to={`/resource/${item.id}`} state={{ node: { id: selectedNodeId, name: nodeResources.node_name } }} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1 mt-1">
                                查看资源 <Icon name="arrow_forward" className="material-symbols-outlined text-xs"/>
                              </Link>
                            ) : (
                              <span className="text-xs text-gray-400">暂无详情</span>
                            )}
                          </div>
                        ))}
                        {nodeResources.chapter_materials.length > 5 && (
                          <button onClick={() => setShowAllMaterials(!showAllMaterials)}
                            className="text-xs text-cyan-600 hover:text-cyan-700 font-medium w-full text-center py-1">
                            {showAllMaterials ? '收起' : `展开全部 (${nodeResources.chapter_materials.length} 条)`}
                          </button>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无章节资料</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-gray-100 p-8 text-center">
                  <p className="text-sm text-gray-400">无法加载节点资源</p>
                </div>
              )}

              {/* 4. 全部练习集（折叠） */}
              {nodeResources?.full_exercise_set?.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                  <button
                    onClick={() => setShowFullExercises(!showFullExercises)}
                    className="w-full flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2">
                      <div className="p-2 bg-purple-50 rounded-lg text-purple-600">
                        <Icon name="list_alt" className="material-symbols-outlined"/>
                      </div>
                      <h4 className="font-bold text-on-surface text-left">
                        全部练习集
                        <span className="text-xs text-secondary font-normal ml-2">共 {nodeResources.full_exercise_set.length} 题</span>
                      </h4>
                    </div>
                    <Icon name="expand_more" className={`material-symbols-outlined text-gray-400 transition-transform ${showFullExercises ? 'rotate-180' : ''}`}/>
                  </button>
                  {showFullExercises && (
                    <div className="mt-4 space-y-2 max-h-96 overflow-y-auto">
                      {nodeResources.full_exercise_set.slice(0, 10).map((item, i) => (
                        <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 text-[10px] rounded font-bold">
                              {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                            </span>
                          </div>
                          <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                        </div>
                      ))}
                      {nodeResources.full_exercise_set.length > 10 && (
                        <p className="text-xs text-gray-400 text-center pt-2">查看更多请进入练习</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
        </div>
      </main>

      {/* Contextual Floating Action Button */}
      <Link to="/ai-chat" className="fixed bottom-margin right-margin w-14 h-14 bg-cyan-500 text-white rounded-full shadow-2xl flex items-center justify-center hover:scale-110 active:scale-90 transition-all z-50">
        <Icon name="auto_awesome" className="material-symbols-outlined text-2xl"/>
      </Link>
    </div>
  );
}
