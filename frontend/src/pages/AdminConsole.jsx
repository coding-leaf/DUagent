import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import UserManagementPanel from '../components/admin/UserManagementPanel';
import CatalogManagementPanel from '../components/admin/CatalogManagementPanel';
import SystemLogsPanel from '../components/admin/SystemLogsPanel';
import RegistrationCodesPanel from '../components/admin/RegistrationCodesPanel';
import Icon from '../components/Icon';
import { useAuth } from '../context/AuthContext';

export default function AdminConsole() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('users');

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-body-md">
      {/* Top NavBar */}
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur-md font-['Public_Sans'] antialiased">
        <div className="mx-auto flex min-h-20 max-w-[1280px] items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-cyan-700">
              <Icon name="admin_panel_settings" className="material-symbols-outlined text-base" />
              系统管理后台
            </div>
            <div className="flex min-w-0 items-baseline gap-3">
              <h1 className="truncate text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
                智能学习助手
              </h1>
              <span className="hidden truncate text-sm text-slate-500 lg:inline">
                Admin Console
              </span>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            {/* User Pill */}
            <div className="hidden items-center gap-2 rounded-full bg-slate-50 py-1.5 pl-1.5 pr-3 md:flex border border-slate-100">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-cyan-200 bg-cyan-100 text-sm font-bold text-cyan-700">
                {(user?.real_name || user?.username || 'A').charAt(0).toUpperCase()}
              </div>
              <div className="leading-tight">
                <p className="text-xs font-bold text-slate-800">{user?.real_name || user?.username || 'Super Admin'}</p>
                <p className="text-[10px] text-slate-500">超级管理员</p>
              </div>
            </div>

            {/* Logout button */}
            <button
              aria-label="退出登录"
              title="退出登录"
              className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              onClick={() => {
                logout?.();
                navigate('/');
              }}
            >
              <Icon name="logout" className="material-symbols-outlined text-sm"/>
              <span className="hidden lg:inline">退出登录</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Layout */}
      <div className="max-w-[1280px] w-full mx-auto flex flex-1">
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
            <UserManagementPanel />
          )}

          {activeTab === 'catalogs' && (
            <CatalogManagementPanel />
          )}

          {activeTab === 'logs' && (
            <SystemLogsPanel />
          )}

          {activeTab === 'regcodes' && (
            <RegistrationCodesPanel />
          )}
        </main>
      </div>
    </div>
  );
}
