import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { learningService } from '../api/services/learning';
import Sidebar from '../components/Sidebar';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';

export default function LearningPath() {
  const { activeCourseId } = useCourse();
  const [learningPath, setLearningPath] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [nodeResources, setNodeResources] = useState(null);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [showFullExercises, setShowFullExercises] = useState(false);

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
    if (!learningPath?.nodes?.length) return;
    const cpId = learningPath.current_position?.node_id;
    if (cpId) {
      setSelectedNodeId(cpId);
      return;
    }
    const ip = learningPath.nodes.find(n => n.status === 'in_progress');
    if (ip) { setSelectedNodeId(ip.id); return; }
    const rec = learningPath.nodes.find(n => n.status === 'recommended');
    if (rec) { setSelectedNodeId(rec.id); return; }
    const first = learningPath.nodes.find(n => n.status !== 'pending');
    if (first) { setSelectedNodeId(first.id); return; }
  }, [learningPath]);

  // Fetch resources when selectedNodeId changes
  useEffect(() => {
    if (selectedNodeId) {
      fetchNodeResources(selectedNodeId);
      setShowFullExercises(false);
    }
  }, [selectedNodeId, fetchNodeResources]);

  return (
    <div className="font-body-md bg-background min-h-screen text-on-background">
      {/* TopNavBar Implementation */}
      <Navbar />

      {/* SideNavBar Component */}
      <Sidebar />

      {/* Main Content Canvas */}
      <main className="ml-0 lg:ml-64 pt-16 min-h-screen">
        <div className="max-w-[1280px] mx-auto p-gutter space-y-md">
          {/* Header Section */}
          <header className="flex flex-col md:flex-row md:items-end justify-between gap-md mb-sm">
            <div>
              <h1 className="font-h1 text-h1 text-on-background">学习路径规划</h1>
            </div>
            <div className="flex space-x-sm">
              <div className="flex items-center space-x-xs px-sm py-xs bg-surface-container rounded-full border border-outline-variant">
                <span className="w-2 h-2 rounded-full bg-cyan-500"></span>
                <span className="text-label-sm font-label-sm text-on-surface">分析智能体在线</span>
              </div>
            </div>
          </header>

          {/* Learning Path Visualizer */}
          <section className="bg-surface-container-lowest border border-gray-100 rounded-xl p-md shadow-sm overflow-hidden">
            <div className="flex items-center justify-between mb-lg">
              <h3 className="font-h3 text-h3 flex items-center space-x-sm">
                <span className="material-symbols-outlined text-cyan-600">insights</span>
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
            <div className="relative flex items-center py-xl overflow-x-auto no-scrollbar scroll-smooth min-h-[300px]">
              {loading ? (
                <div className="w-full flex justify-center"><span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span></div>
              ) : (
                <>
                  {/* Path Line */}
                  <div className="absolute top-1/2 left-0 w-full h-[2px] bg-gray-100 -translate-y-1/2 z-0"></div>
                  <div className="absolute top-1/2 left-0 w-[45%] h-[2.5px] bg-cyan-500 -translate-y-1/2 z-0"></div>

                  {learningPath?.nodes.map((node, index) => {
                    if (node.status === 'completed') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 px-sm flex flex-col items-center group w-80 cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-cyan-400 rounded-xl' : ''}`}>
                          <div className="w-12 h-12 rounded-full bg-cyan-500 flex items-center justify-center text-white mb-sm shadow-lg shadow-cyan-500/20 ring-4 ring-white">
                            <span className="material-symbols-outlined">check</span>
                          </div>
                          <div className="bg-white p-sm rounded-xl border border-gray-100 shadow-sm w-full transition-all group-hover:border-cyan-200">
                            <span className="text-label-sm text-cyan-600 font-bold mb-xs block">阶段 {node.order}</span>
                            <p className="text-body-md font-bold mb-xs">{node.name}</p>
                            <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden mb-sm">
                              <div className="h-full bg-cyan-500 w-full"></div>
                            </div>
                          </div>
                        </div>
                      );
                    } else if (node.status === 'in_progress') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 w-80 px-sm flex flex-col items-center group cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-cyan-400 rounded-xl' : ''}`}>
                          <div className="w-16 h-16 rounded-full bg-white border-4 border-cyan-500 flex items-center justify-center text-cyan-600 mb-sm shadow-xl ring-4 ring-white animate-pulse">
                            <span className="material-symbols-outlined text-3xl">play_arrow</span>
                          </div>
                          <div className="bg-white p-md rounded-xl border-2 border-cyan-500 shadow-md w-full relative">
                            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-cyan-500 text-white text-[10px] px-2 py-0.5 rounded-full font-bold">进行中</div>
                            <span className="text-label-sm text-cyan-600 font-bold mb-xs block">阶段 {node.order}</span>
                            <p className="text-body-lg font-bold mb-base">{node.name}</p>
                            <div className="space-y-xs">
                              <div className="flex justify-between text-label-sm text-gray-500">
                                <span>进度: {node.mastery}%</span>
                              </div>
                              <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                                <div className="h-full bg-cyan-500" style={{ width: `${node.mastery}%` }}></div>
                              </div>
                            </div>
                            <div className="mt-md space-y-sm">
                              <div className="bg-surface-container rounded-lg p-sm border border-outline-variant">
                                <p className="text-label-sm font-bold text-on-surface">智能体提示将在路径 Agent 输出接入后展示</p>
                              </div>
                              <Link to="/dashboard" state={{ search: node.name }} className="w-full py-2 bg-primary text-white rounded-lg text-label-sm font-bold flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors">
                                <span className="material-symbols-outlined text-sm">auto_stories</span>前往资源库继续闯关
                              </Link>
                            </div>
                          </div>
                        </div>
                      );
                    } else if (node.status === 'recommended') {
                      return (
                        <div key={node.id}
                          onClick={() => setSelectedNodeId(node.id)}
                          className={`relative z-10 flex-shrink-0 w-72 px-sm flex flex-col items-center group cursor-pointer ${node.id === selectedNodeId ? 'ring-2 ring-cyan-400 rounded-xl' : ''}`}>
                          <div className="w-12 h-12 rounded-full bg-cyan-100 flex items-center justify-center text-cyan-600 mb-sm border-2 border-cyan-200">
                            <span className="material-symbols-outlined">auto_awesome</span>
                          </div>
                          <div className="bg-white p-sm rounded-xl border border-cyan-200 shadow-sm w-full">
                            <span className="text-label-sm text-cyan-600 font-bold mb-xs block">阶段 {node.order}</span>
                            <p className="text-body-md font-bold mb-xs">{node.name}</p>
                            <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden mb-sm">
                              <div className="h-full bg-cyan-300 w-0"></div>
                            </div>
                            <p className="text-[11px] text-cyan-500">推荐预习节点</p>
                          </div>
                        </div>
                      );
                    } else {
                      return (
                        <div key={node.id} className={`relative z-10 flex-shrink-0 w-64 px-sm flex flex-col items-center ${index > 2 ? 'opacity-40' : 'opacity-60'} grayscale group hover:opacity-100 transition-all`}>
                          <div className="w-12 h-12 rounded-full bg-surface-container-highest flex items-center justify-center text-gray-400 mb-sm border-2 border-white">
                            <span className="material-symbols-outlined">lock</span>
                          </div>
                          <div className="bg-white p-sm rounded-xl border border-gray-100 shadow-sm w-full">
                            <span className="text-label-sm text-gray-400 font-bold mb-xs block">阶段 {node.order}</span>
                            <p className="text-body-md font-bold mb-xs">{node.name}</p>
                            <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden">
                              <div className="h-full bg-gray-300 w-0"></div>
                            </div>
                            <div className="mt-sm text-[12px] text-gray-400 flex items-center">
                              <span className="material-symbols-outlined text-sm mr-1">exercise</span>待开启节点
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
                <span className="material-symbols-outlined text-cyan-600">library_books</span>
                当前节点资源
                {nodeResources?.node_name && (
                  <span className="text-body-md text-secondary font-normal">— {nodeResources.node_name}</span>
                )}
              </h3>

              {resourcesLoading ? (
                <div className="flex justify-center py-12">
                  <span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span>
                </div>
              ) : nodeResources ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* 1. 薄弱点讲解 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-orange-50 rounded-lg text-orange-600">
                        <span className="material-symbols-outlined">lightbulb</span>
                      </div>
                      <h4 className="font-bold text-on-surface">薄弱点讲解</h4>
                    </div>
                    {nodeResources.weak_point_tutorials?.length > 0 ? (
                      <div className="space-y-3">
                        {nodeResources.weak_point_tutorials.map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <p className="text-sm font-bold text-on-surface mb-1">{item.title}</p>
                            <p className="text-xs text-secondary line-clamp-2 mb-2">{item.content || ''}</p>
                            {item.id ? (
                              <Link to={`/resource/${item.id}`} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1">
                                查看资源 <span className="material-symbols-outlined text-xs">arrow_forward</span>
                              </Link>
                            ) : (
                              <span className="text-xs text-gray-400">暂无详情</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400 py-4 text-center">该节点暂无薄弱点讲解</p>
                    )}
                  </div>

                  {/* 2. 节点练习 */}
                  <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                        <span className="material-symbols-outlined">quiz</span>
                      </div>
                      <h4 className="font-bold text-on-surface">节点练习</h4>
                    </div>
                    {nodeResources.exercises?.length > 0 ? (
                      <div className="space-y-3">
                        {nodeResources.exercises.map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-[10px] rounded font-bold">
                                {item.type === 'single_choice' ? '单选' : item.type === 'multi_choice' ? '多选' : item.type}
                              </span>
                            </div>
                            <p className="text-xs text-secondary line-clamp-2">{item.content || ''}</p>
                          </div>
                        ))}
                        <Link to="/quiz" className="w-full block text-center py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 transition-colors">
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
                        <span className="material-symbols-outlined">menu_book</span>
                      </div>
                      <h4 className="font-bold text-on-surface">章节资料</h4>
                    </div>
                    {nodeResources.chapter_materials?.length > 0 ? (
                      <div className="space-y-3">
                        {nodeResources.chapter_materials.map((item, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-lg border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] rounded font-bold">
                                {item.type || '资料'}
                              </span>
                              <p className="text-sm font-bold text-on-surface">{item.title}</p>
                            </div>
                            {item.id ? (
                              <Link to={`/resource/${item.id}`} className="text-xs text-cyan-600 hover:text-cyan-700 font-medium flex items-center gap-1 mt-1">
                                查看资源 <span className="material-symbols-outlined text-xs">arrow_forward</span>
                              </Link>
                            ) : (
                              <span className="text-xs text-gray-400">暂无详情</span>
                            )}
                          </div>
                        ))}
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
                        <span className="material-symbols-outlined">list_alt</span>
                      </div>
                      <h4 className="font-bold text-on-surface text-left">
                        全部练习集
                        <span className="text-xs text-secondary font-normal ml-2">共 {nodeResources.full_exercise_set.length} 题</span>
                      </h4>
                    </div>
                    <span className={`material-symbols-outlined text-gray-400 transition-transform ${showFullExercises ? 'rotate-180' : ''}`}>
                      expand_more
                    </span>
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
        <span className="material-symbols-outlined text-2xl">auto_awesome</span>
      </Link>
    </div>
  );
}
