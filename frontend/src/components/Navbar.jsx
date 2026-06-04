import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCourse } from '../context/CourseContext';

export default function Navbar({ searchTerm, onSearch }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { courses, activeCourseId, changeCourse } = useCourse();
  const [showDropdown, setShowDropdown] = useState(false);

  const isActive = (path) => location.pathname === path;

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="fixed top-0 w-full z-50 bg-white/85 backdrop-blur-md border-b border-gray-100 shadow-sm font-['Public_Sans']">
      <div className="flex items-center justify-between px-6 h-16 max-w-[1280px] mx-auto">
        
        {/* Brand & Course Selector */}
        <div className="flex items-center space-x-md">
          <Link to="/dashboard" className="text-xl font-bold tracking-tight text-cyan-600 hover:opacity-90 transition-opacity">
            数据结构智能助手
          </Link>
          
          {courses && courses.length > 0 && (
            <div className="relative">
              <select
                value={activeCourseId || ''}
                onChange={(e) => changeCourse(e.target.value)}
                className="bg-cyan-50 border border-cyan-100 text-cyan-700 font-bold px-3 py-1 rounded-full text-xs outline-none cursor-pointer focus:ring-2 focus:ring-cyan-500 max-w-[180px] transition-all hover:bg-cyan-100"
              >
                {courses.map(c => (
                  <option key={c.id} value={c.id} className="text-on-surface bg-white font-normal">
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Navigation Tabs */}
        <div className="hidden md:flex items-center space-x-8">
          <Link
            to="/profile"
            className={`transition-colors ${isActive('/profile') ? 'text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1' : 'text-gray-600 hover:text-cyan-500'}`}
          >
            个人信息
          </Link>
          <Link
            to="/learning-path"
            className={`transition-colors ${isActive('/learning-path') ? 'text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1' : 'text-gray-600 hover:text-cyan-500'}`}
          >
            路径规划
          </Link>
          <Link
            to="/dashboard"
            className={`transition-colors ${isActive('/dashboard') ? 'text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1' : 'text-gray-600 hover:text-cyan-500'}`}
          >
            资源库
          </Link>
          <Link
            to="/ai-chat"
            className={`transition-colors ${isActive('/ai-chat') ? 'text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1' : 'text-gray-600 hover:text-cyan-500'}`}
          >
            AI答疑
          </Link>
          <Link
            to="/learning-effects"
            className={`transition-colors ${isActive('/learning-effects') ? 'text-cyan-600 font-semibold border-b-2 border-cyan-500 pb-1' : 'text-gray-600 hover:text-cyan-500'}`}
          >
            学习效果
          </Link>
        </div>

        {/* Right side controls */}
        <div className="flex items-center space-x-4">
          
          {/* Conditional Search Input (For Dashboard integration) */}
          {onSearch !== undefined && (
            <div className="relative hidden lg:block">
              <input
                className="w-48 pl-8 pr-4 py-1.5 bg-surface-container-lowest border border-outline-variant rounded-full text-xs focus:outline-none focus:ring-2 focus:ring-primary-container transition-all"
                placeholder="搜索资源..."
                type="text"
                value={searchTerm || ''}
                onChange={(e) => onSearch(e.target.value)}
              />
              <span className="material-symbols-outlined absolute left-2.5 top-2 text-gray-400 text-sm">search</span>
            </div>
          )}

          <button className="p-2 hover:bg-gray-50 rounded-lg transition-all active:scale-95 duration-200">
            <span className="material-symbols-outlined text-gray-600">notifications</span>
          </button>
          
          {/* User Profile Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="w-8 h-8 rounded-full bg-surface-container-high overflow-hidden border border-outline-variant cursor-pointer focus:outline-none flex items-center justify-center"
            >
              <img
                alt="用户头像"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDIZ6HO5HA-odVe8eyF37yBdDVqfay9WuU9hiH5bUmPQ7FHVUvaaDZxx-umrUXutVljxyDA8RZg_DaakLk5239e-wEBGWbcvlz6m8ugJDjJkfWVXu3go6THqG3cG20AZz_Fo9e3nQQaFkyLTMljw6gQ7C9zzMSbkb9zWAcMi735c3jXolvzaKkf1ukO4JFCIGvZKAEYUotf7YS7Eh9YXEBhXk-zbyI3drYFjCejkZNYy2Xw_yQjYjF31dF20X5HAXjP5TdmPPzYQVXQ"
                className="w-full h-full object-cover"
              />
            </button>

            {showDropdown && (
              <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-100 rounded-xl shadow-lg py-2 z-50">
                <div className="px-4 py-2 border-b border-gray-50 text-left">
                  <p className="text-sm font-bold text-on-surface truncate">{user?.real_name || user?.username || '学生账户'}</p>
                  <p className="text-xs text-gray-400 truncate">{user?.email || ''}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-sm">logout</span>
                  退出登录
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
