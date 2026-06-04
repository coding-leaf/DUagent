
import { Link, useNavigate } from 'react-router-dom';

export default function ResourceDetail() {
  const navigate = useNavigate();

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

          {/* Reading Progress Card */}
          <div className="p-4 rounded-xl bg-surface-container-low space-y-3">
            <h4 className="text-label-sm text-outline uppercase font-bold">阅读进度</h4>
            <div className="w-full bg-surface-container-highest h-2 rounded-full overflow-hidden">
              <div className="bg-primary-container h-full w-[65%]"></div>
            </div>
            <div className="flex justify-between text-label-sm">
              <span>已完成 65%</span>
              <span>3.2k 字 / 4.8k 字</span>
            </div>
          </div>

          {/* Time Metrics */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-white border border-outline-variant rounded-xl flex flex-col items-center text-center">
              <span className="material-symbols-outlined text-primary mb-1">timer</span>
              <span className="text-[10px] text-outline">当前阅读</span>
              <span className="font-bold text-on-surface">12m</span>
            </div>
            <div className="p-3 bg-white border border-outline-variant rounded-xl flex flex-col items-center text-center">
              <span className="material-symbols-outlined text-secondary mb-1">schedule</span>
              <span className="text-[10px] text-outline">建议用时</span>
              <span className="font-bold text-on-surface">25m</span>
            </div>
          </div>

          {/* Keywords */}
          <div className="space-y-2">
            <h4 className="text-label-sm text-outline uppercase font-bold px-2">核心关键词</h4>
            <div className="flex flex-wrap gap-2 px-2">
              <span className="px-2 py-1 bg-surface-container-high text-on-surface-variant rounded text-xs border border-outline-variant">二叉平衡树</span>
              <span className="px-2 py-1 bg-surface-container-high text-on-surface-variant rounded text-xs border border-outline-variant">AVL旋转</span>
              <span className="px-2 py-1 bg-surface-container-high text-on-surface-variant rounded text-xs border border-outline-variant">递归遍历</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Canvas */}
      <main className="ml-0 lg:ml-64 min-h-screen pt-16">
        <div className="max-w-[1280px] mx-auto px-6 py-10 grid grid-cols-12 gap-gutter">
          
          {/* Document Display Section */}
          <div className="col-span-12 lg:col-span-8 space-y-gutter">
            <article className="bg-white p-10 rounded-xl shadow-[0px_4px_20px_rgba(0,0,0,0.04)] border border-outline-variant hover:shadow-lg transition-shadow duration-300">
              <header className="mb-8 border-b border-surface-container-highest pb-6">
                <div className="flex items-center gap-2 mb-2">
                  <span className="px-3 py-1 bg-cyan-100 text-cyan-800 rounded-full text-xs font-bold">深度解析</span>
                  <span className="text-outline text-label-sm">更新于 2023.10.15</span>
                </div>
                <h1 className="text-h1 font-h1 text-on-surface mb-4">深入理解 AVL 树：平衡二叉搜索树的原理与实现</h1>
                <p className="text-body-lg text-on-surface-variant leading-relaxed">
                  在数据结构中，平衡性是保证查找效率的关键。AVL 树作为最早被发明的自平衡二叉搜索树，通过引入“平衡因子”概念，在每次插入或删除后通过旋转操作维持树的高度平衡。
                </p>
              </header>

              <section className="prose prose-slate max-w-none space-y-6 text-on-surface-variant">
                <h2 className="text-h2 font-h2 text-primary border-l-4 border-primary pl-4">1. 什么是平衡因子？</h2>
                <p className="text-body-md">
                  AVL 树中任何节点的两个子树的高度最大差别为 1，因此它也被称为高度平衡树。增加和删除可能需要通过一次或多次树旋转来重新平衡这个树。
                </p>

                {/* Dynamic Visual Component */}
                <div className="my-8 rounded-xl overflow-hidden border border-outline-variant bg-surface-container-lowest p-6">
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-label-sm font-bold text-primary">结构可视化：AVL 树右旋 (LL)</span>
                    <span className="material-symbols-outlined text-outline cursor-pointer hover:text-primary transition-colors">zoom_in</span>
                  </div>
                  <div className="aspect-video relative rounded-lg overflow-hidden bg-slate-50 flex items-center justify-center">
                    <img 
                      className="object-cover w-full h-full opacity-90 transition-transform duration-500 hover:scale-105" 
                      src="https://lh3.googleusercontent.com/aida-public/AB6AXuAobrmGpOJaUR7Xe-fGbU5--OxvqrMMlbfKm2tdmbCWvOV2VFROdDd_lF7iAABdX8a2nxp4-hLzA5kSbh2lzL78aMofbL06hCM2YafuaxCFCxy0rLZoq-HaYrrZ6aYv5PpTO0NzuKLeGhaTsOp1FqO3uGGfHHGz8fgoPDiWl_JfOiDFkMNsP0TxMpTRBuS2F88jzByrvvqMdytllO5wGq0tvhpLGH74i_lVJMf6qg56ygiUUHL5skrFsrBls2THC4zxH3zAORzI6NoV"
                      alt="AVL Tree Visualization"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent pointer-events-none"></div>
                    <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur px-3 py-1 rounded text-xs font-mono shadow-sm">
                      Agent ID: DS-042 | Rendering Status: Optimized
                    </div>
                  </div>
                </div>

                <h2 className="text-h2 font-h2 text-primary border-l-4 border-primary pl-4">2. 旋转机制详解</h2>
                <p className="text-body-md">
                  当树失去平衡时，AVL 树执行四种旋转操作之一：左旋、右旋、左右双旋和右左双旋。这些操作不仅维持了二叉搜索树的性质（左小右大），还压缩了树的高度，确保了 O(log n) 的最坏情况查找时间。
                </p>

                <div className="grid grid-cols-2 gap-4 my-6">
                  <div className="p-4 bg-surface-container-low rounded-lg border-l-4 border-on-tertiary-container hover:bg-surface-container-high transition-colors">
                    <h4 className="font-bold text-on-tertiary-container mb-1">左旋 (RR)</h4>
                    <p className="text-xs">当右子树的右侧插入节点导致失衡时触发。</p>
                  </div>
                  <div className="p-4 bg-surface-container-low rounded-lg border-l-4 border-on-tertiary-container hover:bg-surface-container-high transition-colors">
                    <h4 className="font-bold text-on-tertiary-container mb-1">右旋 (LL)</h4>
                    <p className="text-xs">当左子树的左侧插入节点导致失衡时触发。</p>
                  </div>
                </div>
              </section>

              <footer className="mt-12 pt-8 border-t border-surface-container-highest flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <button className="flex items-center gap-2 text-outline hover:text-primary transition-colors cursor-pointer">
                    <span className="material-symbols-outlined">thumb_up</span>
                    <span className="text-label-sm">有用 (128)</span>
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

          {/* Interaction Panel / Quiz Trigger */}
          <div className="col-span-12 lg:col-span-4 space-y-6">
            {/* Learning Assistant Card */}
            <div className="bg-white p-6 rounded-xl shadow-[0px_4px_20px_rgba(0,0,0,0.04)] border border-outline-variant relative overflow-hidden hover:-translate-y-1 transition-transform duration-300">
              <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-50 rounded-full -mr-10 -mt-10 blur-2xl"></div>
              <div className="relative z-10 flex flex-col items-center text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-primary-container flex items-center justify-center text-white shadow-inner">
                  <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
                </div>
                <div>
                  <h3 className="text-h3 font-h3 text-on-surface">DS智能体建议</h3>
                  <p className="text-label-sm text-on-surface-variant mt-2 px-4">
                    您已完成 AVL 树理论部分的阅读。根据系统分析，现在是进行实践巩固的最佳时机。
                  </p>
                </div>
                
                <div className="w-full space-y-2 pt-4">
                  <div className="flex justify-between items-center text-xs text-outline px-1">
                    <span>预期掌握程度</span>
                    <span className="text-primary font-bold">85%</span>
                  </div>
                  <div className="w-full h-1.5 bg-surface-container-highest rounded-full">
                    <div className="w-[85%] h-full bg-primary-container rounded-full"></div>
                  </div>
                </div>

                <Link to="/quiz" className="w-full py-4 bg-primary-container text-on-primary-container rounded-xl font-bold text-lg flex items-center justify-center gap-3 shadow-xl shadow-primary-container/30 hover:scale-[1.02] active:scale-[0.98] transition-all group cursor-pointer">
                  <span className="material-symbols-outlined group-hover:rotate-12 transition-transform">exercise</span>
                  开始互动练习
                </Link>
              </div>
            </div>

            {/* Learning Path Map */}
            <div className="bg-white p-6 rounded-xl border border-outline-variant hover:shadow-md transition-shadow duration-300">
              <h4 className="text-label-sm font-bold text-outline mb-6 flex items-center justify-between">
                学习路径图
                <span className="material-symbols-outlined text-xs">open_in_new</span>
              </h4>
              <div className="space-y-4 relative">
                <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-surface-container-highest"></div>
                
                <div className="flex items-center gap-4 relative">
                  <div className="w-6 h-6 rounded-full bg-cyan-500 border-4 border-white shadow-sm flex items-center justify-center z-10">
                    <span className="material-symbols-outlined text-[10px] text-white">check</span>
                  </div>
                  <div className="flex-1 text-sm text-outline">二叉搜索树 (BST) 基础</div>
                </div>

                <div className="flex items-center gap-4 relative">
                  <div className="w-6 h-6 rounded-full bg-cyan-500 border-4 border-white shadow-sm flex items-center justify-center z-10">
                    <span className="material-symbols-outlined text-[10px] text-white">check</span>
                  </div>
                  <div className="flex-1 text-sm text-on-surface font-semibold">AVL 树原理</div>
                </div>

                <div className="flex items-center gap-4 relative">
                  <div className="w-6 h-6 rounded-full bg-white border-4 border-surface-container-highest shadow-sm z-10"></div>
                  <div className="flex-1 text-sm text-outline">B-树与红黑树对比</div>
                </div>

                <div className="flex items-center gap-4 relative">
                  <div className="w-6 h-6 rounded-full bg-white border-4 border-surface-container-highest shadow-sm z-10"></div>
                  <div className="flex-1 text-sm text-outline">实际应用案例</div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}
