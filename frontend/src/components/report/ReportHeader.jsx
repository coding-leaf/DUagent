import Icon from '../Icon';

const ROLE_MAP = { teacher: '教师', admin: '管理员' };

export default function ReportHeader({ courseName, user, onLogout }) {
  return (
    <header className="fixed top-0 w-full z-50 flex justify-between items-center px-gutter h-20 bg-white border-b border-outline-variant shadow-sm font-['Public_Sans'] antialiased">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-on-surface">{courseName}</h1>
        <span className="px-2 py-1 bg-surface-container-high text-primary font-bold text-xs rounded uppercase">教学控制台</span>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-cyan-500/10 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-sm">
            {String(user?.real_name || user?.username || '教').charAt(0)}
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-on-surface">{user?.real_name || user?.username || '教师'}</span>
            <span className="text-[10px] text-outline uppercase tracking-wider">
              {ROLE_MAP[user?.role] || '教师'}
            </span>
          </div>
        </div>
        <div className="h-8 w-[1px] bg-outline-variant"></div>
        <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-error hover:bg-error-container/20 rounded-lg transition-colors cursor-pointer" onClick={onLogout}>
          <Icon name="logout" className="material-symbols-outlined text-sm"/>
          退出登入
        </button>
      </div>
    </header>
  );
}
