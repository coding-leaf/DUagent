import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import UserManagementPanel from '../components/admin/UserManagementPanel';
import CatalogManagementPanel from '../components/admin/CatalogManagementPanel';
import SystemLogsPanel from '../components/admin/SystemLogsPanel';
import RegistrationCodesPanel from '../components/admin/RegistrationCodesPanel';
import Icon from '../components/Icon';

export default function AdminConsole() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('users');

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
