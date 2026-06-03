import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { profileService } from '../api/services/profile';

export default function LearningEffects() {
  const navigate = useNavigate();
  const [effectsData, setEffectsData] = useState(null);

  useEffect(() => {
    profileService.getLearningEffects().then(res => {
      if (res.code === 200) {
        setEffectsData(res.data);
      }
    }).catch(console.error);
  }, []);


  return (
    <div className="bg-background text-on-surface font-body-md min-h-screen">
      {/* TopNavBar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-gray-100 shadow-sm font-['Public_Sans'] antialiased">
        <div className="flex items-center justify-between px-6 h-16 max-w-[1280px] mx-auto">
          <div className="text-xl font-bold tracking-tight text-cyan-600">数据结构智能助手</div>
          <div className="hidden md:flex items-center space-x-8">
            <Link to="/profile" className="text-gray-600 hover:text-cyan-500 transition-colors">个人信息</Link>
            <Link to="/learning-path" className="text-gray-600 hover:text-cyan-500 transition-colors">路径规划</Link>
            <Link to="/dashboard" className="text-gray-600 hover:text-cyan-500 transition-colors">资源库</Link>
            <Link to="/ai-chat" className="text-gray-600 hover:text-cyan-500 transition-colors">AI答疑</Link>
            <Link to="/learning-effects" className="text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1">学习效果</Link>
          </div>
          <div className="flex items-center space-x-4">
            <button className="p-2 hover:bg-gray-50 rounded-lg transition-all active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-gray-600">notifications</span>
            </button>
            <button className="p-2 hover:bg-gray-50 rounded-lg transition-all active:scale-95 duration-200 cursor-pointer">
              <span className="material-symbols-outlined text-gray-600">settings</span>
            </button>
            <div className="w-8 h-8 rounded-full bg-surface-container-high overflow-hidden border border-outline-variant cursor-pointer" onClick={() => navigate('/profile')}>
              <img alt="用户头像" className="w-full h-full object-cover" src="https://lh3.googleusercontent.com/aida-public/AB6AXuDIZ6HO5HA-odVe8eyF37yBdDVqfay9WuU9hiH5bUmPQ7FHVUvaaDZxx-umrUXutVljxyDA8RZg_DaakLk5239e-wEBGWbcvlz6m8ugJDjJkfWVXu3go6THqG3cG20AZz_Fo9e3nQQaFkyLTMljw6gQ7C9zzMSbkb9zWAcMi735c3jXolvzaKkf1ukO4JFCIGvZKAEYUotf7YS7Eh9YXEBhXk-zbyI3drYFjCejkZNYy2Xw_yQjYjF31dF20X5HAXjP5TdmPPzYQVXQ" />
            </div>
          </div>
        </div>
      </nav>

      {/* SideNavBar */}
      <aside className="h-full w-64 fixed left-0 top-16 bg-white border-r border-gray-100 flex flex-col py-6 space-y-2 font-['Public_Sans'] text-sm hidden lg:flex">
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
            <Link to="/dashboard" className="flex items-center space-x-3 px-4 py-3 rounded-lg text-gray-500 hover:bg-gray-50 transition-all duration-200 ease-in-out cursor-pointer hover:pl-5">
              <span className="material-symbols-outlined">library_books</span>
              <span className="font-body-md">资源库</span>
            </Link>
          </div>
        </nav>
        <div className="px-6 mt-auto">
          <button onClick={() => navigate('/dashboard')} className="w-full py-3 bg-primary-container text-on-primary-container rounded-xl font-bold active:scale-95 transition-all shadow-sm cursor-pointer">
            启动新任务
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="lg:pl-64 pt-24 pb-12 px-6 max-w-[1280px] mx-auto min-h-screen">
        {/* Header Section */}
        <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="font-h1 text-h1 text-on-surface text-4xl font-bold mb-2">学习效果展示</h1>
            <p className="text-body-md text-outline mt-2 text-slate-500">基于多智能体系统的实时数据结构掌握度分析</p>
          </div>
          <div className="flex gap-3">
            <button className="flex items-center px-4 py-2 bg-white border border-outline-variant rounded-xl font-label-sm text-label-sm text-on-surface-variant hover:bg-surface-container transition-all cursor-pointer">
              <span className="material-symbols-outlined mr-2">download</span> 导出报告
            </button>
            <button className="flex items-center px-4 py-2 bg-primary-container text-on-primary-container rounded-xl font-label-sm text-label-sm font-bold shadow-sm hover:brightness-110 active:scale-95 transition-all cursor-pointer">
              <span className="material-symbols-outlined mr-2">refresh</span> 重新评估
            </button>
          </div>
        </div>

        {/* Bento Grid Layout */}
        <div className="grid grid-cols-12 gap-6">
          {/* AI Insight Card (Full Width Span) */}
          <div className="col-span-12 lg:col-span-8 bg-white/80 backdrop-blur-md rounded-xl p-6 flex flex-col md:flex-row gap-6 items-start shadow-sm border border-gray-100">
            <div className="flex-shrink-0 w-16 h-16 bg-cyan-100 rounded-full flex items-center justify-center">
              <span className="material-symbols-outlined text-cyan-600 text-3xl" style={{ fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
            </div>
            <div>
              <h3 className="font-h3 text-xl font-bold mb-2 flex items-center">
                AI 智能分析报告
                <span className="ml-3 px-2 py-0.5 bg-cyan-100 text-cyan-700 text-[10px] rounded-full font-bold">实时分析</span>
              </h3>
              <p className="font-body-md text-slate-600 leading-relaxed">
                根据过去 7 天的学习轨迹，您的<span className="text-cyan-600 font-bold">“非线性数据结构”</span>掌握程度提升了 32%。系统检测到您在“B+树删除操作”中存在逻辑瓶颈，建议协同“排序智能体”进行专项练习。资源使用分布显示，您对视觉化节点的交互反馈频率远高于纯文本阅读，后续路径将自动增加动态演示权重。
              </p>
            </div>
          </div>

          {/* Exercise/Test Mastery Chart */}
          <div className="col-span-12 lg:col-span-4 bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100">
            <h3 className="font-h3 text-xl font-bold mb-4 flex items-center">
              <span className="material-symbols-outlined mr-2 text-cyan-600">assessment</span> 练习掌握度
            </h3>
            <div className="flex flex-col gap-4 mt-6">
              {effectsData?.knowledge_nodes?.map((node, i) => {
                let p = 0;
                if (node.status === 'mastered') p = 95;
                else if (node.status === 'familiar') p = 78;
                else if (node.status === 'weak') p = 42;
                else p = 20;

                return (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-between text-sm font-bold text-slate-700">
                      <span>{node.name}</span>
                      <span className="text-cyan-600">{p}%</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-cyan-500" style={{ width: `${p}%` }}></div>
                    </div>
                  </div>
                );
              })}
              {(!effectsData?.knowledge_nodes || effectsData.knowledge_nodes.length === 0) && (
                <div className="text-slate-400 text-sm">暂无数据</div>
              )}
            </div>
          </div>

          {/* Path Progression Table */}
          <div className="col-span-12 lg:col-span-7 bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100">
            <h3 className="font-h3 text-xl font-bold mb-6">学习路径进度</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="pb-3 text-sm text-slate-400">模块名称</th>
                    <th className="pb-3 text-sm text-slate-400">当前状态</th>
                    <th className="pb-3 text-sm text-slate-400">平均耗时</th>
                    <th className="pb-3 text-sm text-slate-400">掌握评分</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  <tr className="group hover:bg-slate-50 transition-colors">
                    <td className="py-4 font-body-md text-slate-700">线性表与栈</td>
                    <td className="py-4">
                      <span className="px-3 py-1 bg-green-50 text-green-600 rounded-full text-xs font-bold">已完成</span>
                    </td>
                    <td className="py-4 font-body-md text-slate-500">4.2h</td>
                    <td className="py-4 font-bold text-cyan-600">A+</td>
                  </tr>
                  <tr className="group hover:bg-slate-50 transition-colors">
                    <td className="py-4 font-body-md text-slate-700">散列表(Hash)</td>
                    <td className="py-4">
                      <span className="px-3 py-1 bg-cyan-50 text-cyan-600 rounded-full text-xs font-bold">进行中</span>
                    </td>
                    <td className="py-4 font-body-md text-slate-500">1.5h</td>
                    <td className="py-4 font-bold text-cyan-600">B</td>
                  </tr>
                  <tr className="group hover:bg-slate-50 transition-colors">
                    <td className="py-4 font-body-md text-slate-700">红黑树进阶</td>
                    <td className="py-4">
                      <span className="px-3 py-1 bg-gray-100 text-gray-500 rounded-full text-xs font-bold">待解锁</span>
                    </td>
                    <td className="py-4 font-body-md text-slate-400">--</td>
                    <td className="py-4 font-bold text-slate-400">--</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Resource Usage Distribution */}
          <div className="col-span-12 lg:col-span-5 bg-white/80 backdrop-blur-md rounded-xl p-6 shadow-sm border border-gray-100 flex flex-col">
            <h3 className="font-h3 text-xl font-bold mb-6">资源反馈分布</h3>
            <div className="flex-grow flex items-center justify-center relative min-h-[220px]">
              {/* Simulated Pie/Donut Chart via SVG */}
              <svg className="w-48 h-48 transform -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" fill="transparent" r="15.915" stroke="#e5eeff" strokeWidth="3"></circle>
                <circle cx="18" cy="18" fill="transparent" r="15.915" stroke="#00d1ff" strokeDasharray="60 40" strokeDashoffset="25" strokeWidth="3"></circle>
                <circle cx="18" cy="18" fill="transparent" r="15.915" stroke="#00677f" strokeDasharray="25 75" strokeDashoffset="85" strokeWidth="3"></circle>
                <circle cx="18" cy="18" fill="transparent" r="15.915" stroke="#aec4c7" strokeDasharray="15 85" strokeDashoffset="100" strokeWidth="3"></circle>
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-4xl font-bold text-cyan-600">128</span>
                <span className="text-sm text-slate-500">总交互数</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-6">
              <div className="flex items-center">
                <div className="w-3 h-3 rounded-full bg-cyan-400 mr-2"></div>
                <span className="text-sm text-slate-600">动态演示 (60%)</span>
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 rounded-full bg-cyan-800 mr-2"></div>
                <span className="text-sm text-slate-600">代码调试 (25%)</span>
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 rounded-full bg-slate-300 mr-2"></div>
                <span className="text-sm text-slate-600">理论文档 (15%)</span>
              </div>
              <div className="flex items-center">
                <div className="w-3 h-3 rounded-full bg-slate-100 mr-2"></div>
                <span className="text-sm text-slate-600">其它 (5%)</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
