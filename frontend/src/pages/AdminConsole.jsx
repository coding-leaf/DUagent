import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '../api/services/admin';
import CourseCatalogDrawer from '../components/admin/CourseCatalogDrawer';
import { useAuth } from '../context/AuthContext';
import { getErrorMessage } from '../utils/apiError';

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const getLogRows = (data) => data?.logs || data || [];

export default function AdminConsole() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('users');
  
  // User Data State
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [userActionError, setUserActionError] = useState('');
  const [removingUserId, setRemovingUserId] = useState(null);
  const [disabledUserIds, setDisabledUserIds] = useState(() => new Set());
  
  // Log Data State
  const [agentLogs, setAgentLogs] = useState([]);
  const [operationLogs, setOperationLogs] = useState([]);
  const [activeLogType, setActiveLogType] = useState('agent');
  const [loadingLogs, setLoadingLogs] = useState(false);

  // Course Catalog State
  const [catalogs, setCatalogs] = useState([]);
  const [selectedCatalog, setSelectedCatalog] = useState(null);
  const [loadingCatalogs, setLoadingCatalogs] = useState(false);
  const [catalogError, setCatalogError] = useState('');
  const [newCatalogTitle, setNewCatalogTitle] = useState('');
  const [newCatalogDescription, setNewCatalogDescription] = useState('');
  const [creatingCatalog, setCreatingCatalog] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoadingUsers(true);
    setUserActionError('');
    try {
      const res = await adminService.getUsers({ keyword: searchQuery });
      if (res.code === 200) {
        setUsers(res.data.users || []);
      }
    } catch (e) {
      console.error(e);
      setUserActionError(getErrorMessage(e, '用户列表加载失败'));
    } finally {
      setLoadingUsers(false);
    }
  }, [searchQuery]);

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const [agentRes, systemRes] = await Promise.all([
        adminService.getAgentLogs(),
        adminService.getSystemLogs()
      ]);
      if (agentRes.code === 200) {
        setAgentLogs(getLogRows(agentRes.data));
      }
      if (systemRes.code === 200) {
        setOperationLogs(getLogRows(systemRes.data));
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingLogs(false);
    }
  }, []);

  const fetchCatalogs = useCallback(async () => {
    setLoadingCatalogs(true);
    setCatalogError('');
    try {
      const res = await adminService.getCourseCatalogs();
      if (res.code === 200) {
        const nextCatalogs = res.data?.catalogs || [];
        setCatalogs(nextCatalogs);
        setSelectedCatalog((current) => {
          if (!current) return current;
          return nextCatalogs.find((catalog) => catalog.id === current.id) || current;
        });
      }
    } catch (e) {
      console.error(e);
      setCatalogError(getErrorMessage(e, '课程资源库加载失败'));
    } finally {
      setLoadingCatalogs(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (activeTab === 'users') {
        fetchUsers();
      } else if (activeTab === 'logs') {
        fetchLogs();
      } else if (activeTab === 'catalogs') {
        fetchCatalogs();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [activeTab, fetchUsers, fetchLogs, fetchCatalogs]);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchUsers();
  };

  const handleRemoveUser = async (targetUser) => {
    const isCurrentUser = targetUser.id === user?.id || targetUser.email === user?.email;
    if (isCurrentUser || disabledUserIds.has(targetUser.id)) return;
    const confirmed = window.confirm(`确认停用用户 ${targetUser.username || targetUser.email || targetUser.id}？`);
    if (!confirmed) return;

    setRemovingUserId(targetUser.id);
    setUserActionError('');
    try {
      const res = await adminService.removeUser(targetUser.id);
      if (res.code === 200) {
        setDisabledUserIds((prev) => new Set(prev).add(targetUser.id));
        await fetchUsers();
      } else {
        setUserActionError(res.message || '停用用户失败');
      }
    } catch (e) {
      console.error(e);
      setUserActionError(getErrorMessage(e, '停用用户失败'));
    } finally {
      setRemovingUserId(null);
    }
  };

  const handleCreateCatalog = async (event) => {
    event.preventDefault();
    const title = newCatalogTitle.trim();
    const description = newCatalogDescription.trim();
    if (!title || creatingCatalog) return;

    setCreatingCatalog(true);
    setCatalogError('');
    try {
      const res = await adminService.createCourseCatalog({ title, description });
      if (res.code === 201 || res.code === 200) {
        setNewCatalogTitle('');
        setNewCatalogDescription('');
        await fetchCatalogs();
      } else {
        setCatalogError(res.message || '课程资源库创建失败');
      }
    } catch (e) {
      console.error(e);
      setCatalogError(getErrorMessage(e, '课程资源库创建失败'));
    } finally {
      setCreatingCatalog(false);
    }
  };

  const handleOpenCatalog = (catalog) => {
    setSelectedCatalog(catalog);
  };

  const handleCloseCatalog = () => {
    setSelectedCatalog(null);
  };

  const visibleLogs = activeLogType === 'agent' ? agentLogs : operationLogs;

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
            <button onClick={() => navigate('/admin')} className="text-sm text-slate-300 hover:text-white transition-colors cursor-pointer">
              管理首页
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
            onClick={() => setActiveTab('catalogs')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'catalogs' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <span className="material-symbols-outlined text-lg">library_books</span>
            课程资源库
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'logs' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <span className="material-symbols-outlined text-lg">terminal</span>
            系统日志
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

              {userActionError && (
                <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {userActionError}
                </div>
              )}

              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="px-6 py-4 font-medium">用户 ID</th>
                      <th className="px-6 py-4 font-medium">用户名 / 邮箱</th>
                      <th className="px-6 py-4 font-medium">角色</th>
                      <th className="px-6 py-4 font-medium">创建时间</th>
                      <th className="px-6 py-4 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loadingUsers ? (
                      <tr><td colSpan="5" className="text-center py-12 text-slate-400">加载中...</td></tr>
                    ) : users.length === 0 ? (
                      <tr><td colSpan="5" className="text-center py-12 text-slate-400">暂无匹配用户</td></tr>
                    ) : (
                      users.map(u => {
                        const isCurrentUser = u.id === user?.id || u.email === user?.email;
                        const isDisabledLocally = disabledUserIds.has(u.id);
                        const isActionDisabled = isCurrentUser || isDisabledLocally || removingUserId === u.id;
                        return (
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
                              }`}>{u.role?.toUpperCase() || 'UNKNOWN'}</span>
                            </td>
                            <td className="px-6 py-4 text-slate-500 text-xs">{formatDateTime(u.created_at)}</td>
                            <td className="px-6 py-4 text-right">
                              <button
                                type="button"
                                onClick={() => handleRemoveUser(u)}
                                disabled={isActionDisabled}
                                className={`inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                                  isActionDisabled
                                    ? 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400'
                                    : 'cursor-pointer border-red-200 bg-white text-red-600 hover:bg-red-50'
                                }`}
                                title={
                                  isCurrentUser
                                    ? '不可停用当前登录用户'
                                    : isDisabledLocally
                                      ? '该用户已停用'
                                      : '停用用户'
                                }
                              >
                                <span className="material-symbols-outlined text-[16px]">person_off</span>
                                {removingUserId === u.id ? '停用中' : isDisabledLocally ? '已停用' : '停用'}
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'catalogs' && (
            <div className="animate-in fade-in duration-500">
              <div className="flex justify-between items-end mb-6">
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 mb-1">课程资源库</h1>
                  <p className="text-sm text-slate-500">维护平台共享课程内容资产，教师开班只能绑定已就绪资源库。</p>
                </div>
                <button onClick={fetchCatalogs} className="flex items-center gap-1 text-cyan-600 hover:underline text-sm font-medium cursor-pointer">
                  <span className="material-symbols-outlined text-[18px]">refresh</span> 刷新资源库
                </button>
              </div>

              <form onSubmit={handleCreateCatalog} className="mb-6 bg-white border border-slate-200 rounded-xl shadow-sm p-5">
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] lg:items-end">
                  <label className="block">
                    <span className="mb-1 block text-xs font-bold text-slate-500">资源库名称</span>
                    <input
                      type="text"
                      value={newCatalogTitle}
                      onChange={(e) => setNewCatalogTitle(e.target.value)}
                      placeholder="输入资源库名称"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition-all focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-bold text-slate-500">描述</span>
                    <input
                      type="text"
                      value={newCatalogDescription}
                      onChange={(e) => setNewCatalogDescription(e.target.value)}
                      placeholder="输入资源库描述"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition-all focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={!newCatalogTitle.trim() || creatingCatalog}
                    className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                      !newCatalogTitle.trim() || creatingCatalog
                        ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                        : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[18px]">add</span>
                    {creatingCatalog ? '创建中' : '创建'}
                  </button>
                </div>
              </form>

              {catalogError && (
                <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {catalogError}
                </div>
              )}

              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
                    <tr>
                      <th className="px-6 py-4 font-medium">资源库</th>
                      <th className="px-6 py-4 font-medium">状态</th>
                      <th className="px-6 py-4 font-medium">资料数</th>
                      <th className="px-6 py-4 font-medium">创建时间</th>
                      <th className="px-6 py-4 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loadingCatalogs ? (
                      <tr><td colSpan="5" className="text-center py-12 text-slate-400">加载中...</td></tr>
                    ) : catalogs.length === 0 ? (
                      <tr><td colSpan="5" className="text-center py-12 text-slate-400">暂无课程资源库</td></tr>
                    ) : (
                      catalogs.map((catalog) => (
                        <tr
                          key={catalog.id}
                          onClick={() => handleOpenCatalog(catalog)}
                          className="cursor-pointer hover:bg-slate-50/50 transition-colors"
                        >
                          <td className="px-6 py-4">
                            <div className="font-bold text-slate-900">{catalog.title || '未命名资源库'}</div>
                            <div className="mt-1 max-w-xl text-xs text-slate-500">{catalog.description || '暂无描述'}</div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-wrap gap-2">
                              <span className="rounded bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">
                                {catalog.status || 'UNKNOWN'}
                              </span>
                              {catalog.knowledge_status && (
                                <span className="rounded bg-cyan-50 px-2.5 py-1 text-xs font-bold text-cyan-700">
                                  {catalog.knowledge_status}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-slate-600">
                            {catalog.material_count ?? catalog.materials_count ?? catalog.materials?.length ?? '—'}
                          </td>
                          <td className="px-6 py-4 text-slate-500 text-xs">{formatDateTime(catalog.created_at)}</td>
                          <td className="px-6 py-4 text-right">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                handleOpenCatalog(catalog);
                              }}
                              className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-cyan-200 bg-white px-3 py-1.5 text-xs font-medium text-cyan-700 transition-colors hover:bg-cyan-50"
                            >
                              <span className="material-symbols-outlined text-[16px]">folder_managed</span>
                              管理资料
                            </button>
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
                  <h1 className="text-2xl font-bold text-slate-900 mb-1">系统日志</h1>
                  <p className="text-sm text-slate-500">查看 Agent 运行记录与系统操作事件。</p>
                </div>
                <button onClick={fetchLogs} className="flex items-center gap-1 text-cyan-600 hover:underline text-sm font-medium cursor-pointer">
                  <span className="material-symbols-outlined text-[18px]">refresh</span> 刷新日志
                </button>
              </div>

              <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1">
                <button
                  type="button"
                  onClick={() => setActiveLogType('agent')}
                  className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                    activeLogType === 'agent' ? 'bg-cyan-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Agent 日志
                </button>
                <button
                  type="button"
                  onClick={() => setActiveLogType('system')}
                  className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                    activeLogType === 'system' ? 'bg-cyan-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  系统日志
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
                  ) : visibleLogs.length === 0 ? (
                    <div className="text-slate-500">
                      {activeLogType === 'agent' ? '暂无 Agent 日志' : '暂无系统日志'}
                    </div>
                  ) : activeLogType === 'agent' ? (
                    agentLogs.map((log) => (
                      <div key={`${log.timestamp}-${log.endpoint}-${log.agent_type}`} className="flex gap-4 hover:bg-white/5 p-1 rounded transition-colors group">
                        <span className="text-slate-500 flex-shrink-0 w-52">[{formatDateTime(log.timestamp)}]</span>
                        <span className={`font-bold flex-shrink-0 w-28 ${
                          log.status === 'error' ? 'text-red-400' : 'text-cyan-400'
                        }`}>
                          {log.status?.toUpperCase() || 'INFO'}
                        </span>
                        <span className="text-emerald-400 flex-shrink-0 w-36">[{log.agent_type || '—'}]</span>
                        <span className="flex-1 break-all text-slate-200">
                          {log.endpoint}{log.error_message ? ` — ${log.error_message}` : ''}
                          <span className="ml-2 text-xs text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">
                            (Lat: {log.latency_ms}ms, Tokens: {log.tokens_used})
                          </span>
                        </span>
                      </div>
                    ))
                  ) : (
                    operationLogs.map((log) => (
                      <div key={`${log.timestamp}-${log.event_type}-${log.user_id || 'system'}`} className="flex gap-4 hover:bg-white/5 p-1 rounded transition-colors group">
                        <span className="text-slate-500 flex-shrink-0 w-52">[{formatDateTime(log.timestamp)}]</span>
                        <span className={`font-bold flex-shrink-0 w-32 ${
                          log.event_type === 'system_error' || log.event_type === 'security' ? 'text-red-400' : 'text-cyan-400'
                        }`}>
                          {log.event_type?.toUpperCase() || 'OPERATION'}
                        </span>
                        <span className="text-emerald-400 flex-shrink-0 w-40">[{log.user_id || 'system'}]</span>
                        <span className="flex-1 break-all text-slate-200">
                          {log.description || '—'}
                          <span className="ml-2 text-xs text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">
                            (IP: {log.ip_address || '—'}, Detail: {log.detail ? JSON.stringify(log.detail) : '{}'})
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
      <CourseCatalogDrawer
        catalog={selectedCatalog}
        open={Boolean(selectedCatalog)}
        onClose={handleCloseCatalog}
        onChanged={fetchCatalogs}
      />
    </div>
  );
}
