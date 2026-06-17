import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '../api/services/admin';
import { catalogService } from '../api/services/catalog';
import CourseCatalogDrawer from '../components/admin/CourseCatalogDrawer';
import SystemLogsPanel from '../components/admin/SystemLogsPanel';
import RegistrationCodesPanel from '../components/admin/RegistrationCodesPanel';
import { useAuth } from '../context/AuthContext';
import { getErrorMessage } from '../utils/apiError';
import Icon from '../components/Icon';

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

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
  const [resetPasswordTarget, setResetPasswordTarget] = useState(null);
  const [resetPasswordValue, setResetPasswordValue] = useState('');
  const [resetPasswordError, setResetPasswordError] = useState('');
  const [resettingPassword, setResettingPassword] = useState(false);

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

  const fetchCatalogs = useCallback(async () => {
    setLoadingCatalogs(true);
    setCatalogError('');
    try {
      const res = await catalogService.getCourseCatalogs();
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
      } else if (activeTab === 'catalogs') {
        fetchCatalogs();
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [activeTab, fetchUsers, fetchCatalogs]);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchUsers();
  };

  const handleRemoveUser = async (targetUser) => {
    const isCurrentUser = targetUser.id === user?.id || targetUser.email === user?.email;
    if (isCurrentUser || !targetUser.is_active) return;
    const confirmed = window.confirm(`确认停用用户 ${targetUser.username || targetUser.email || targetUser.id}？`);
    if (!confirmed) return;

    setRemovingUserId(targetUser.id);
    setUserActionError('');
    try {
      const res = await adminService.removeUser(targetUser.id);
      if (res.code === 200) {
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

  const handleResetPassword = async () => {
    if (!resetPasswordTarget || !resetPasswordValue.trim()) return;
    if (!/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,32}$/.test(resetPasswordValue)) {
      setResetPasswordError('密码需包含大小写字母和数字，8-32位');
      return;
    }
    setResettingPassword(true);
    setResetPasswordError('');
    try {
      const res = await adminService.updateUser(resetPasswordTarget.id, { new_password: resetPasswordValue });
      if (res.code === 200) {
        setResetPasswordTarget(null);
        setResetPasswordValue('');
      } else {
        setResetPasswordError(res.message || '重置失败');
      }
    } catch (e) {
      setResetPasswordError(getErrorMessage(e, '重置失败'));
    } finally {
      setResettingPassword(false);
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
      const res = await catalogService.createCourseCatalog({ title, description });
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

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-body-md">
      {/* Top NavBar */}
      <nav className="fixed top-0 w-full z-40 bg-slate-900 text-white shadow-md">
        <div className="flex items-center justify-between px-6 h-16 max-w-[1440px] mx-auto">
          <div className="flex items-center gap-3">
            <Icon name="admin_panel_settings" className="material-symbols-outlined text-cyan-400"/>
            <div className="text-xl font-bold tracking-tight">智能学习助手 <span className="font-light text-cyan-400">Admin</span></div>
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
            <Icon name="group" className="material-symbols-outlined text-lg"/>
            用户管控
          </button>
          <button
            onClick={() => setActiveTab('catalogs')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'catalogs' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Icon name="library_books" className="material-symbols-outlined text-lg"/>
            课程资源库
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'logs' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Icon name="terminal" className="material-symbols-outlined text-lg"/>
            系统日志
          </button>
          <button
            onClick={() => setActiveTab('regcodes')}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all font-medium text-sm cursor-pointer ${
              activeTab === 'regcodes' ? 'bg-cyan-50 text-cyan-700 border-r-4 border-cyan-500' : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Icon name="key" className="material-symbols-outlined text-lg"/>
            注册码管理
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
                  <Icon name="search" className="material-symbols-outlined absolute left-3 top-2.5 text-slate-400 text-[18px]"/>
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
                        const isDisabled = u.is_active === false;
                        const isActionDisabled = isCurrentUser || isDisabled || removingUserId === u.id;
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
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  type="button"
                                  onClick={() => { setResetPasswordTarget(u); setResetPasswordValue(''); setResetPasswordError(''); }}
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
                                  title="重置密码"
                                >
                                  <Icon name="lock_reset" className="material-symbols-outlined text-[16px]"/>
                                  重置密码
                                </button>
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
                                      : isDisabled
                                        ? '该用户已停用'
                                        : '停用用户'
                                  }
                                >
                                  <Icon name="person_off" className="material-symbols-outlined text-[16px]"/>
                                  {removingUserId === u.id ? '停用中' : isDisabled ? '已停用' : '停用'}
                                </button>
                              </div>
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
                  <Icon name="refresh" className="material-symbols-outlined text-[18px]"/> 刷新资源库
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
                    <Icon name="add" className="material-symbols-outlined text-[18px]"/>
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
                            <div className="mt-1 max-w-[576px] text-xs text-slate-500">{catalog.description || '暂无描述'}</div>
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
                              <Icon name="folder_managed" className="material-symbols-outlined text-[16px]"/>
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
            <SystemLogsPanel />
          )}

          {activeTab === 'regcodes' && (
            <RegistrationCodesPanel />
          )}
        </main>
      </div>
      <CourseCatalogDrawer
        catalog={selectedCatalog}
        open={Boolean(selectedCatalog)}
        onClose={handleCloseCatalog}
        onChanged={fetchCatalogs}
      />

      {resetPasswordTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-[384px] mx-4 p-6">
            <h2 className="text-lg font-bold text-slate-900 mb-1">重置密码</h2>
            <p className="text-sm text-slate-500 mb-4">
              为 <span className="font-semibold text-slate-700">{resetPasswordTarget.username}</span>（{resetPasswordTarget.email}）设置新密码
            </p>
            <input
              type="password"
              value={resetPasswordValue}
              onChange={(e) => { setResetPasswordValue(e.target.value); setResetPasswordError(''); }}
              placeholder="新密码（大小写字母+数字，8-32位）"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 mb-3"
              autoFocus
            />
            {resetPasswordError && (
              <p className="text-xs text-red-500 mb-3">{resetPasswordError}</p>
            )}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => { setResetPasswordTarget(null); setResetPasswordValue(''); setResetPasswordError(''); }}
                className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleResetPassword}
                disabled={resettingPassword || !resetPasswordValue.trim()}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-cyan-600 text-white hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
              >
                {resettingPassword ? '重置中…' : '确认重置'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
