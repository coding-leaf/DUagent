import { Link, useLocation } from 'react-router-dom';
import Icon from './Icon';

export default function Sidebar() {
  const location = useLocation();
  const isActive = (path) => location.pathname === path;

  return (
    <aside className="h-full w-64 fixed left-0 top-16 bg-white border-r border-gray-100 flex flex-col py-6 space-y-2 font-['Public_Sans'] text-sm hidden lg:flex z-40">
      <div className="px-6 mb-6">
        <div className="flex items-center space-x-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-primary-container flex items-center justify-center text-white">
            <Icon name="smart_toy" className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}/>
          </div>
          <div>
            <h3 className="text-lg font-black text-cyan-600 leading-tight">智能学习助手</h3>
            <p className="text-[10px] text-gray-400 uppercase tracking-widest">多智能体学习系统</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 space-y-1">
        <div className="px-4">
          <Link to="/learning-path" className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ease-in-out cursor-pointer hover:pl-5 ${isActive('/learning-path') ? 'bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500' : 'text-gray-500 hover:bg-gray-50'}`}>
            <Icon name="account_tree" className="material-symbols-outlined"/>
            <span className="font-body-md">学习节点</span>
          </Link>
          <Link to="/dashboard" className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ease-in-out cursor-pointer hover:pl-5 ${isActive('/dashboard') ? 'bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500' : 'text-gray-500 hover:bg-gray-50'}`}>
            <Icon name="library_books" className="material-symbols-outlined" style={{ fontVariationSettings: '"FILL" 1' }}/>
            <span className="font-body-md">资源库</span>
          </Link>
          <Link to="/personalized-resources" className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ease-in-out cursor-pointer hover:pl-5 ${isActive('/personalized-resources') ? 'bg-cyan-50 text-cyan-600 border-r-4 border-cyan-500' : 'text-gray-500 hover:bg-gray-50'}`}>
            <Icon name="psychology" className="material-symbols-outlined"/>
            <span className="font-body-md">个性化资源</span>
          </Link>
        </div>
      </nav>
    </aside>
  );
}
