import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { authService } from '../api/services/auth';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  const [captchaQuestion, setCaptchaQuestion] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');
  const [captchaCode, setCaptchaCode] = useState('');

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchCaptcha = async () => {
    try {
      const response = await authService.getCaptcha();
      if (response.code === 200) {
        setCaptchaQuestion(response.data.captcha_question);
        setCaptchaToken(response.data.captcha_token);
      }
    } catch (err) {
      console.error('获取验证码失败:', err);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCaptcha();
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await authService.login({
        email: email,
        password: password,
        captcha_token: captchaToken,
        captcha_code: captchaCode,
      });

      if (response.code === 200) {
        const token = response.data.token;
        const userData = response.data.user;

        login(token, userData);

        const userRole = userData?.role;
        if (userRole === 'admin' || userRole === 'teacher') {
          navigate('/teacher');
        } else {
          navigate('/dashboard');
        }
      } else {
        setError(response.message || '登录失败，请检查账号密码');
        fetchCaptcha();
      }
    } catch (err) {
      fetchCaptcha();
      if (err.response && err.response.data) {
        setError(err.response.data.message || '登录失败');
      } else {
        setError('网络错误，请稍后重试');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex-grow flex flex-col lg:flex-row min-h-screen">
      {/* Sidebar: Welcome/Info Section (Left) */}
      <section className="lg:w-[40%] xl:w-[35%] relative min-h-[400px] lg:min-h-screen flex flex-col p-gutter lg:p-xl overflow-hidden">
        {/* Background Image Integration */}
        <div className="absolute inset-0 z-0">
          <img
            alt="Data Structure Visualization"
            className="w-full h-full object-cover"
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuAiTJ_GAvDOuHMFdWLbS_M3BaLYbfT_iMZXA7ArGiPh-z_Kab_HsFo9xK-2e808gHSfRdF-Php-Eyburwv7uA_G-8_j_4iF6L0qtv7KKE1OIzzECIYeOxzF8OuMgIcnVXy3hye1g4vlO0tW8JAm-zNRp_ijrtayb8VDfhPlz-19NB2vj16XtZdOHUMHKYj4rKv2yueL-y6DcA2vpuzgeDOLFBDSuvbS15e3N4iTGeMO_-iS5CTLvmkN3OguQGyepZMnLuShCBAIE2Xd"
          />
          <div className="absolute inset-0 bg-primary/40 backdrop-blur-[2px] mix-blend-multiply"></div>
          <div className="absolute inset-0 bg-gradient-to-br from-primary/80 via-primary/40 to-transparent"></div>
        </div>

        {/* Content Overlay */}
        <div className="relative z-10 flex flex-col h-full text-white justify-between">
          <div>
            {/* Brand */}
            <div className="flex items-center space-x-xs mb-xl">
              <span className="material-symbols-outlined text-primary-fixed" style={{ fontSize: '32px' }}>hub</span>
              <h1 className="font-['Public_Sans'] text-2xl font-black tracking-tighter">数据结构智能助手</h1>
            </div>
            
            <div className="space-y-lg my-auto">
              <div className="space-y-sm">
                <div className="inline-flex items-center px-3 py-1 rounded-full bg-white/10 border border-white/20 backdrop-blur-sm">
                  <span className="material-symbols-outlined text-primary-fixed text-sm mr-2">neurology</span>
                  <span className="text-label-sm font-bold uppercase tracking-wider">Multi-Agent Learning System</span>
                </div>
                <h2 className="font-h1 leading-tight text-3xl lg:text-4xl text-left">
                  数据结构智能助手 <br />
                  <span className="text-primary-fixed">核心调度器</span>
                </h2>
                <p className="font-body-lg text-white/80 max-w-[448px] text-left text-sm lg:text-base">
                  基于大模型的个性化资源生成与学习多智能体系统。探索数据结构的奥秘，由智能体引导的沉浸式学习体验。
                </p>
              </div>

              {/* Features Summary */}
              <div className="grid grid-cols-1 gap-md text-left pt-4">
                <div className="bg-white/10 backdrop-blur-md p-md rounded-xl border border-white/20 shadow-sm border-l-4 border-primary-fixed">
                  <span className="material-symbols-outlined text-primary-fixed mb-2">account_tree</span>
                  <h4 className="font-h3 text-sm font-bold mb-1">结构化解析</h4>
                  <p className="text-label-sm text-white/70">利用多智能体协作，深度拆解复杂数据结构逻辑。</p>
                </div>
                <div className="bg-white/10 backdrop-blur-md p-md rounded-xl border border-white/20 shadow-sm border-l-4 border-white/40">
                  <span className="material-symbols-outlined text-white/60 mb-2">auto_awesome</span>
                  <h4 className="font-h3 text-sm font-bold mb-1">个性化生成</h4>
                  <p className="text-label-sm text-white/70">根据学习进度动态生成个性化习题与解析资源。</p>
                </div>
              </div>
            </div>
          </div>

          {/* Status Card (Footer of Sidebar) */}
          <div className="mt-xl p-md rounded-xl bg-white/5 border border-white/10 flex items-center space-x-md text-left">
            <div className="w-3 h-3 rounded-full bg-green-400 animate-pulse"></div>
            <div>
              <p className="text-label-sm font-bold opacity-80 uppercase tracking-widest text-xs">System Status</p>
              <p className="text-body-md text-white/90 text-sm">智能体集群已就绪，等待指令...</p>
            </div>
          </div>
        </div>
      </section>

      {/* Right Side: Forms (Main Content) */}
      <section className="flex-grow flex flex-col justify-center items-center p-gutter lg:p-xl bg-surface-container-low min-h-screen">
        <div className="max-w-[1000px] w-full">
          {/* Mobile Branding (Hidden on Large Screens) */}
          <div className="lg:hidden flex flex-col items-center mb-lg">
            <div className="flex items-center space-x-xs mb-2">
              <span className="material-symbols-outlined text-primary" style={{ fontSize: '24px' }}>hub</span>
              <h2 className="font-['Public_Sans'] text-xl font-black text-on-surface">数据结构智能助手</h2>
            </div>
            <p className="text-label-sm text-secondary uppercase tracking-widest text-xs">Multi-Agent Learning System</p>
          </div>

          <div className="glass-panel p-gutter lg:p-xl rounded-2xl shadow-xl border border-surface-container-highest bg-white/80 backdrop-blur-md">
            {/* Tabs */}
            <div className="flex justify-center border-b border-surface-container-high mb-gutter">
              <button className="px-xl py-sm font-h3 text-lg text-primary border-b-4 border-primary font-bold">登入</button>
              <Link to="/register" className="px-xl py-sm font-h3 text-lg text-secondary hover:text-on-surface transition-colors">注册账号</Link>
            </div>

            {/* Centered Container for the Login Form */}
            <div className="max-w-[448px] mx-auto">
              <div className="text-center mb-gutter">
                <h3 className="font-h2 text-2xl text-on-surface font-bold">欢迎登入</h3>
                <p className="text-body-md text-secondary text-sm">请使用您的账户信息访问系统</p>
              </div>

              {/* Login Form */}
              {error && (
                <div className="flex items-center p-4 mb-4 text-error bg-error-container rounded-lg border border-error/20" role="alert">
                  <span className="material-symbols-outlined mr-2">error</span>
                  <span className="text-label-sm font-bold">{error}</span>
                </div>
              )}
              <form onSubmit={handleSubmit} className="space-y-md text-left">
                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">电子邮箱 (Email)</label>
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-sm">mail</span>
                    <input
                      className={`w-full pl-10 pr-4 py-3 rounded-lg border bg-surface-container-lowest focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all ${error ? 'border-error ring-1 ring-error/20' : 'border-outline-variant'}`}
                      placeholder="输入您的邮箱"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">密码 (Password)</label>
                  <div className="relative">
                    <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-sm">lock</span>
                    <input
                      className={`w-full pl-10 pr-4 py-3 rounded-lg border bg-surface-container-lowest focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all ${error ? 'border-error ring-1 ring-error/20' : 'border-outline-variant'}`}
                      placeholder="输入您的密码"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">验证码 (Captcha)</label>
                  <div className="flex space-x-sm">
                    <div className="relative flex-grow">
                      <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-sm">verified_user</span>
                      <input
                        className={`w-full pl-10 pr-4 py-3 rounded-lg border bg-surface-container-lowest focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-all ${error ? 'border-error ring-1 ring-error/20' : 'border-outline-variant'}`}
                        placeholder="输入计算结果"
                        type="text"
                        value={captchaCode}
                        onChange={(e) => setCaptchaCode(e.target.value)}
                        required
                      />
                    </div>
                    <button
                      type="button"
                      onClick={fetchCaptcha}
                      className="px-md bg-secondary-container text-on-secondary-container font-h3 text-sm rounded-lg hover:brightness-105 active:scale-95 transition-all whitespace-nowrap cursor-pointer flex items-center justify-center min-w-[120px]"
                      title="点击刷新验证码"
                    >
                      {captchaQuestion || '加载中...'}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      className="rounded text-primary focus:ring-primary w-4 h-4"
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                    />
                    <span className="text-label-sm text-secondary text-xs">记住我</span>
                  </label>
                  <a className="text-label-sm text-primary hover:underline font-medium text-xs" href="#">忘记密码?</a>
                </div>

                <button
                  className="w-full py-4 bg-primary text-on-primary font-h3 rounded-lg shadow-md hover:brightness-110 active:scale-95 transition-all flex items-center justify-center space-x-2 text-lg font-bold disabled:opacity-70 disabled:cursor-not-allowed"
                  type="submit"
                  disabled={loading}
                >
                  <span>{loading ? '登入中...' : '登入系统'}</span>
                  {!loading && <span className="material-symbols-outlined">login</span>}
                  {loading && <span className="material-symbols-outlined animate-spin">refresh</span>}
                </button>
              </form>

              <div className="text-center pt-md mt-gutter border-t border-surface-container-low">
                <p className="text-label-sm text-secondary text-xs">
                  还没有账号? <Link to="/register" className="text-primary font-bold hover:underline">立即注册</Link>
                </p>
              </div>
            </div>
          </div>

          {/* Footer Info */}
          <footer className="mt-xl text-center">
            <p className="text-label-sm text-outline mb-xs text-xs">© 2024 数据结构智能助手 核心调度器. All rights reserved.</p>
            <div className="flex justify-center space-x-md text-label-sm text-secondary font-medium text-xs">
              <a className="hover:text-primary transition-colors" href="#">隐私政策</a>
              <a className="hover:text-primary transition-colors" href="#">服务条款</a>
              <span className="text-outline-variant">|</span>
              <span>By: 害虫杀手队</span>
            </div>
          </footer>
        </div>
      </section>
    </main>
  );
}
