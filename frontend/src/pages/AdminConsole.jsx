import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '../api/services/admin';

export default function AdminConsole() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('users');
  
  // User Data State
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Log Data State
  const [agentLogs, setAgentLogs] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const res = await adminService.getUsers({ search: searchQuery });
      if (res.code === 200) {
        setUsers(res.data.users);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingUsers(false);
    }
  }, [searchQuery]);

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const [agentRes] = await Promise.all([
        adminService.getAgentLogs(),
        adminService.getSystemLogs()
      ]);
      if (agentRes.code === 200) {
        // Handle database array structure or direct mock list structure
        setAgentLogs(agentRes.data.logs || agentRes.data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingLogs(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeTab === 'users') {
        fetchUsers();
      } else {
        fetchLogs();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [activeTab, fetchUsers, fetchLogs]);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchUsers();
  };

  const toggleUserStatus = async (userId, currentStatus) => {
    try {
      await adminService.updateUser(userId, { status: currentStatus === 'active' ? 'banned' : 'active' });
      // Optimitic update
      setUsers(users.map(u => u.id === userId ? { ...u, status: currentStatus === 'active' ? 'banned' : 'active' } : u));
    } catch (e) {
      console.error(e);
    }
  };

  const deleteUser = async (userId) => {
    if (!window.confirm('确认彻底删除该用户吗？')) return;
    try {
      await adminService.removeUser(userId);
      setUsers(users.filter(u => u.id !== userId));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-body-md">
      {/* Top NavBar */}
      <nav className="fixed top-0 w-full z-40 bg-slate-900 text-white shadow-md">
        <div className="flex items-center justify-between px-6 h-16 max-w-[1440px] mx-auto">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-cyan-400">admin_panel_settings</span>
            <div className="text-xl font-bold tracking-tight">DS_MASTERY_AI <span className="font-light text-cyan-400">Admin</span></div>
          </div>
          <div className="flex items-center space-x-6">
            <button onClick={() => navigate('/dashboard')} className="text-sm text-slate-300 hover:text-white transition-colors cursor-pointer">
              返回前台
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center font-bold border border-cyan-500/30">
                A
              </div>
              <span className="text-sm font-medium">Super Admin</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Layout */}
      <div className="pt-16 max-w-[1440px] mx-auto flex min-h-screen">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-slate-200 p-6 flex flex-col gap-2">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 px-3">系统管理</p>
          <button
            onClick={() => setActiveTab('users')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'users' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <span className="material-symbols-outlined text-lg">group</span>
            用户管控
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'logs' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <span className="material-symbols-outlined text-lg">terminal</span>
            智能体日志
          </button>
        </aside>

        {/* Content Area */}
        <main className="flex-1 p-8 bg-slate-50/50">
          
          {activeTab === 'users' && (
            <div className="animate-in fade-in duration-500">
              <div className="flex justify-between items-end mb-6">
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 mb-1">用户管控</h1>
                  <p className="text-sm text-slate-500">管理平台的所有学生与教师账号权限。</p>
                </div>
                <form onSubmit={handleSearch} className="relative">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="搜索用户名或邮箱..."
                    className="pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 w-64 transition-all outline-none"
                  />
                  <span className="material-symbols-outlined absolute left-3 top-2.5 text-slate-400 text-[18px]">search</span>
                  <button type="submit" className="hidden">搜索</button>
                </form>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="px-6 py-4 font-medium">用户 ID</th>
                      <th className="px-6 py-4 font-medium">用户名 / 邮箱</th>
                      <th className="px-6 py-4 font-medium">角色</th>
                      <th className="px-6 py-4 font-medium">状态</th>
                      <th className="px-6 py-4 font-medium">最后登录</th>
                      <th className="px-6 py-4 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loadingUsers ? (
                      <tr><td colSpan="6" className="text-center py-12 text-slate-400">加载中...</td></tr>
                    ) : users.length === 0 ? (
                      <tr><td colSpan="6" className="text-center py-12 text-slate-400">暂无匹配用户</td></tr>
                    ) : (
                      users.map(u => (
                        <tr key={u.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-6 py-4 font-mono text-xs text-slate-500">{u.id}</td>
                          <td className="px-6 py-4">
                            <div className="font-bold text-slate-900">{u.username}</div>
                            <div className="text-xs text-slate-500">{u.email}</div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                              u.role === 'admin' ? 'bg-purple-100 text-purple-700' :
                              u.role === 'teacher' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'
                            }`}>{u.role.toUpperCase()}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`flex items-center gap-1.5 text-xs font-bold ${
                              u.status === 'active' ? 'text-emerald-600' : 'text-red-500'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${u.status === 'active' ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
                              {u.status === 'active' ? '正常' : '已封禁'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-slate-500 text-xs">
                            {new Date(u.last_login).toLocaleString()}
                          </td>
                          <td className="px-6 py-4 text-right space-x-2">
                            {u.role !== 'admin' && (
                              <>
                                <button
                                  onClick={() => toggleUserStatus(u.id, u.status)}
                                  className={`px-3 py-1.5 rounded text-xs font-bold transition-colors cursor-pointer ${
                                    u.status === 'active' ? 'bg-orange-50 text-orange-600 hover:bg-orange-100' : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
                                  }`}
                                >
                                  {u.status === 'active' ? '封禁' : '解封'}
                                </button>
                                <button
                                  onClick={() => deleteUser(u.id)}
                                  className="px-3 py-1.5 rounded bg-red-50 text-red-600 hover:bg-red-100 text-xs font-bold transition-colors cursor-pointer"
                                >
                                  删除
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="animate-in fade-in duration-500 h-full flex flex-col">
              <div className="flex justify-between items-end mb-6">
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 mb-1">多智能体协同日志</h1>
                  <p className="text-sm text-slate-500">实时监控底层 Agent 调度与推断过程。</p>
                </div>
                <button onClick={fetchLogs} className="flex items-center gap-1 text-cyan-600 hover:underline text-sm font-medium cursor-pointer">
                  <span className="material-symbols-outlined text-[18px]">refresh</span> 刷新日志
                </button>
              </div>

              <div className="flex-1 bg-[#0f172a] rounded-xl border border-slate-800 shadow-xl overflow-hidden flex flex-col font-mono text-sm">
                <div className="flex items-center gap-2 px-4 py-3 bg-[#1e293b] border-b border-slate-800">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                  <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                  <span className="ml-4 text-xs text-slate-400 font-sans tracking-wider uppercase">Orchestrator Terminal</span>
                </div>
                <div className="p-4 overflow-y-auto flex-1 space-y-2 text-slate-300">
                  {loadingLogs ? (
                    <div className="text-cyan-500 animate-pulse">Connecting to Agent Mesh...</div>
                  ) : (
                    agentLogs.map((log) => (
                      <div key={log.id} className="flex gap-4 hover:bg-white/5 p-1 rounded transition-colors group">
                        <span className="text-slate-500 flex-shrink-0 w-48">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className={`font-bold flex-shrink-0 w-28 ${
                          log.level === 'ERROR' ? 'text-red-400' :
                          log.level === 'WARN' ? 'text-amber-400' :
                          log.level === 'DEBUG' ? 'text-purple-400' : 'text-cyan-400'
                        }`}>
                          {log.level}
                        </span>
                        <span className="text-emerald-400 flex-shrink-0 w-36">[{log.agent}]</span>
                        <span className="flex-1 break-all text-slate-200">
                          {log.message}
                          <span className="ml-2 text-xs text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">
                            (Lat: {log.metadata.latency}, Tokens: {log.metadata.tokens_used})
                          </span>
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
