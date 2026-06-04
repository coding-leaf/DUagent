import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { learningService } from '../api/services/learning';
import Sidebar from '../components/Sidebar';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';

export default function LearningPath() {
  const navigate = useNavigate();
  const { activeCourseId } = useCourse();
  const [learningPath, setLearningPath] = useState(null);
  const [loading, setLoading] = useState(true);

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

  const getCategoryForNode = (nodeName) => {
    if (!nodeName) return '全部';
    if (nodeName.includes('Hash') || nodeName.includes('散列') || nodeName.includes('哈希')) return '哈希表专题';
    if (nodeName.includes('冲突')) return '冲突处理策略';
    if (nodeName.includes('习题') || nodeName.includes('练习')) return '习题集';
    return '全部';
  };

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
                        <div key={node.id} className="relative z-10 flex-shrink-0 px-sm flex flex-col items-center group w-80">
                          <div className="w-12 h-12 rounded-full bg-cyan-500 flex items-center justify-center text-white mb-sm shadow-lg shadow-cyan-500/20 ring-4 ring-white">
                            <span className="material-symbols-outlined">check</span>
                          </div>
                          <div className="bg-white p-sm rounded-xl border border-gray-100 shadow-sm w-full transition-all group-hover:border-cyan-200">
                            <span className="text-label-sm text-cyan-600 font-bold mb-xs block">阶段 {node.order}</span>
                            <p className="text-body-md font-bold mb-xs">{node.name}</p>
                            <div className="h-1 w-full bg-gray-100 rounded-full overflow-hidden mb-sm">
                              <div className="h-full bg-cyan-500 w-full"></div>
                            </div>
                            <div className="space-y-sm pt-sm border-t border-gray-50">
                              <div className="space-y-1">
                                <p className="text-[11px] font-bold text-error">欠缺知识点推荐：</p>
                                <div className="flex flex-wrap gap-1">
                                  <span className="px-1.5 py-0.5 bg-error-container text-on-error-container text-[10px] rounded">尾递归优化</span>
                                </div>
                              </div>
                              <div className="space-y-1">
                                <p className="text-[11px] font-bold text-on-surface-variant">配套习题：</p>
                                <div className="flex flex-col gap-1">
                                  <Link to="/resource/detail" className="text-[10px] text-primary hover:underline flex items-center">
                                    <span className="material-symbols-outlined text-[12px] mr-1">link</span>查看相关资料
                                  </Link>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    } else if (node.status === 'in_progress') {
                      return (
                        <div key={node.id} className="relative z-10 flex-shrink-0 w-80 px-sm flex flex-col items-center group">
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
                                <span>关键缺失: 旋转平衡因子</span>
                              </div>
                              <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                                <div className="h-full bg-cyan-500" style={{ width: `${node.mastery}%` }}></div>
                              </div>
                            </div>
                            <div className="mt-md space-y-sm">
                              <div className="bg-surface-container rounded-lg p-sm border border-outline-variant">
                                <p className="text-label-sm font-bold text-on-surface">智能体提示：</p>
                                <p className="text-[12px] text-on-surface-variant leading-relaxed">检测到在此概念上的平均停留时间过长，建议通过下方的可视化课件巩固。</p>
                              </div>
                              <Link to="/dashboard" state={{ search: node.name, category: getCategoryForNode(node.name) }} className="w-full py-2 bg-primary text-white rounded-lg text-label-sm font-bold flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors">
                                <span className="material-symbols-outlined text-sm">auto_stories</span>前往资源库继续闯关
                              </Link>
                            </div>
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

          {/* Bottom Modules: Recommendations */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter">
            
            {/* 1. Mind Map recommendations */}
            <div className="bg-white rounded-xl border border-gray-100 p-md shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-sm mb-md">
                <div className="p-base bg-cyan-50 rounded-lg text-cyan-600">
                  <span className="material-symbols-outlined">hub</span>
                </div>
                <h4 className="font-h3 text-body-md font-bold">知识导图推荐</h4>
              </div>
              <div className="aspect-video rounded-xl bg-slate-50 border border-gray-100 mb-md overflow-hidden group relative">
                <img alt="知识导图预览" className="w-full h-full object-cover transition-transform group-hover:scale-105" src="https://lh3.googleusercontent.com/aida-public/AB6AXuBnDFl8Run1qwlA-CNLYbe6WNavCtCuJeF1d-9CRy94aVhRou-FrJZ-Wd8xapKIY4TuJ6WxmoJfWnZbTAJutPJj5PuEHx-K9N-3pb3trq0vYBWZhKq1Xt9UnorqQkmq_V5BQVyOMRVMCafz1T0wtS-M3nfH_hdGeyD__WzcZDG1C--NRkCmBtaQQ5aNeGNDMEWEiymmn5q7y5B5JdTMOojSom5ppFXUwEcrvCa5KP0Qe_pSj6BpcrpO83XkJCUNokBNxCVZywj1GyEQ" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent"></div>
              </div>
              <ul className="space-y-sm">
                <li className="flex items-start space-x-base p-sm hover:bg-gray-50 rounded-lg cursor-pointer">
                  <span className="material-symbols-outlined text-sm text-cyan-500 mt-0.5">schema</span>
                  <div>
                    <p className="text-label-sm font-bold">非线性结构全景图</p>
                    <p className="text-[11px] text-gray-400">覆盖树与图的所有基本变换</p>
                  </div>
                </li>
              </ul>
            </div>

            {/* 2. Lecture document recommendations */}
            <div className="bg-white rounded-xl border border-gray-100 p-md shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-sm mb-md">
                <div className="p-base bg-cyan-50 rounded-lg text-cyan-600">
                  <span className="material-symbols-outlined">menu_book</span>
                </div>
                <h4 className="font-h3 text-body-md font-bold">课件讲义推荐</h4>
              </div>
              <div className="space-y-sm">
                <Link to="/resource/detail" className="p-sm bg-surface-container rounded-xl border border-outline-variant flex items-center space-x-sm group cursor-pointer block">
                  <div className="w-12 h-14 bg-white rounded-md shadow-sm flex items-center justify-center text-cyan-600">
                    <span className="material-symbols-outlined">description</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-label-sm font-bold group-hover:text-cyan-600">AVL树：旋转的艺术.pdf</p>
                    <p className="text-[11px] text-gray-400">斯坦福大学 DS101 精选</p>
                  </div>
                </Link>
                <div className="p-sm border border-gray-100 rounded-xl flex items-center space-x-sm group cursor-pointer hover:border-cyan-200">
                  <div className="w-12 h-14 bg-gray-50 rounded-md flex items-center justify-center text-gray-400">
                    <span className="material-symbols-outlined">description</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-label-sm font-bold">哈希冲突与红黑树.pptx</p>
                    <p className="text-[11px] text-gray-400">高效查询机制专题</p>
                  </div>
                </div>
              </div>
              <Link to="/dashboard" state={{ category: '全部' }} className="w-full mt-lg py-2 text-label-sm text-cyan-600 font-bold hover:bg-cyan-50 rounded-lg transition-colors inline-block text-center block">查看更多文档</Link>
            </div>

            {/* 3. Mixed exercise set recommendations */}
            <div className="bg-white rounded-xl border border-gray-100 p-md shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center space-x-sm mb-md">
                <div className="p-base bg-cyan-50 rounded-lg text-cyan-600">
                  <span className="material-symbols-outlined">task_alt</span>
                </div>
                <h4 className="font-h3 text-body-md font-bold">混合练习集推荐</h4>
              </div>
              <div className="bg-gradient-to-br from-cyan-500 to-cyan-600 rounded-xl p-md text-white mb-md relative overflow-hidden">
                <div className="relative z-10">
                  <p className="text-[10px] font-bold uppercase tracking-widest opacity-80">智能体严选</p>
                  <h5 className="text-body-lg font-bold mt-xs">中阶数据结构挑战赛</h5>
                  <p className="text-[12px] opacity-90 mt-base leading-relaxed">包含AVL树、堆排序及图遍历的15道经典面试题。</p>
                  <button onClick={() => navigate('/quiz')} className="mt-md bg-white text-cyan-600 px-md py-base rounded-lg text-label-sm font-bold shadow-lg active:scale-95 transition-all cursor-pointer">开始练习</button>
                </div>
                <span className="material-symbols-outlined absolute -bottom-4 -right-4 text-[120px] opacity-10 rotate-12">extension</span>
              </div>
              <div className="space-y-base">
                <div className="flex items-center justify-between p-sm border-b border-gray-50">
                  <span className="text-label-sm">每日算法打卡</span>
                  <span className="text-[10px] font-bold text-cyan-500 bg-cyan-50 px-2 py-0.5 rounded">难度: 中等</span>
                </div>
                <div className="flex items-center justify-between p-sm border-b border-gray-50">
                  <span className="text-label-sm">时间复杂度专项</span>
                  <span className="text-[10px] font-bold text-tertiary bg-tertiary-container px-2 py-0.5 rounded">难度: 简单</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      </main>

      {/* Contextual Floating Action Button */}
      <Link to="/ai-chat" className="fixed bottom-margin right-margin w-14 h-14 bg-cyan-500 text-white rounded-full shadow-2xl flex items-center justify-center hover:scale-110 active:scale-90 transition-all z-50">
        <span className="material-symbols-outlined text-2xl">auto_awesome</span>
      </Link>
    </div>
  );
}
