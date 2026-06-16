import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { getApiErrorMessage } from '../api/error';
import { authService } from '../api/services/auth';
import Icon from '../components/Icon';

export default function Register() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    username: '',
    fullName: '',
    studentId: '',
    major: '',
    grade: '大一 (Freshman)',
    guidanceLevel: 'L2',
    email: '',
    captchaCode: '',
    password: '',
    confirmPassword: '',
    inviteCode: ''
  });

  const [captchaQuestion, setCaptchaQuestion] = useState('');
  const [captchaToken, setCaptchaToken] = useState('');

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

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.username.trim().length < 3) {
        setError('用户名至少 3 个字符');
        return;
    }
    if (formData.username.trim().length > 20) {
        setError('用户名最多 20 个字符');
        return;
    }
    if (formData.password !== formData.confirmPassword) {
        setError('两次输入的密码不一致，请重新输入');
        return;
    }
    
    setError('');
    setLoading(true);
    
    try {
      const response = await authService.register({
        registration_code: formData.inviteCode,
        email: formData.email,
        password: formData.password,
        username: formData.username,
        real_name: formData.fullName,
        student_id: formData.studentId,
        major: formData.major,
        grade: formData.grade,
        guidance_level: formData.guidanceLevel,
        captcha_token: captchaToken,
        captcha_code: formData.captchaCode
      });
      
      if (response.code === 201 || response.code === 200) {
        navigate('/success');
      } else {
        setError(response.message || '注册失败');
        fetchCaptcha();
      }
    } catch (err) {
      fetchCaptcha();
      setError(getApiErrorMessage(err, '注册失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex-grow flex flex-col lg:flex-row min-h-screen">
      {/* Sidebar: Welcome/Info Section (Left) */}
      <section className="lg:w-[40%] xl:w-[35%] relative min-h-[400px] lg:min-h-screen flex flex-col p-8 lg:p-12 overflow-hidden bg-gradient-to-br from-cyan-600 to-cyan-900">
        {/* Decorative elements */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 pointer-events-none">
          <div className="absolute -top-[10%] -left-[10%] w-[50%] h-[50%] rounded-full bg-cyan-400/20 blur-[80px]"></div>
          <div className="absolute bottom-[10%] -right-[10%] w-[60%] h-[60%] rounded-full bg-blue-500/20 blur-[100px]"></div>
          <div className="absolute top-[40%] left-[20%] w-[40%] h-[40%] rounded-full bg-teal-400/10 blur-[60px]"></div>
        </div>

        {/* Content Overlay */}
        <div className="relative z-10 flex flex-col h-full text-white justify-between">
          <div>
            {/* Brand */}
            <div className="flex items-center space-x-2 mb-16">
              <Icon name="school" className="material-symbols-outlined text-cyan-300" style={{ fontSize: '32px' }}/>
              <h1 className="font-['Plus_Jakarta_Sans',sans-serif] text-2xl font-bold tracking-tight">智能学习助手</h1>
            </div>
            
            <div className="space-y-10 my-auto">
              <div className="space-y-4">
                <div className="inline-flex items-center px-4 py-1.5 rounded-full bg-white/10 border border-white/20 backdrop-blur-md">
                  <Icon name="psychology" className="material-symbols-outlined text-cyan-300 text-sm mr-2"/>
                  <span className="text-xs font-bold uppercase tracking-widest text-cyan-50">EduAgent Platform</span>
                </div>
                <h2 className="font-['Plus_Jakarta_Sans',sans-serif] text-4xl lg:text-5xl font-extrabold leading-tight tracking-tight">
                  开启您的 <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-teal-200">智能学习之旅</span>
                </h2>
                <p className="text-cyan-50/80 max-w-[400px] text-base leading-relaxed mt-4">
                  结合大模型与多智能体技术，为您提供量身定制的学习路径、互动答疑与沉浸式的知识探索体验。
                </p>
              </div>

              {/* Features Summary */}
              <div className="grid grid-cols-1 gap-4 text-left pt-6">
                <div className="bg-white/10 backdrop-blur-md p-5 rounded-2xl border border-white/10 hover:bg-white/15 transition-colors group">
                  <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <Icon name="route" className="material-symbols-outlined text-cyan-300"/>
                  </div>
                  <h4 className="text-base font-bold mb-1 text-white">个性化路径规划</h4>
                  <p className="text-sm text-cyan-50/70 leading-relaxed">动态评估您的掌握程度，实时生成最适合的专属学习节点与挑战。</p>
                </div>
                
                <div className="bg-white/10 backdrop-blur-md p-5 rounded-2xl border border-white/10 hover:bg-white/15 transition-colors group">
                  <div className="w-10 h-10 rounded-full bg-teal-500/20 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                    <Icon name="forum" className="material-symbols-outlined text-teal-300"/>
                  </div>
                  <h4 className="text-base font-bold mb-1 text-white">沉浸式互动引导</h4>
                  <p className="text-sm text-cyan-50/70 leading-relaxed">提供随时随地的 1V1 智能辅导，帮您深度剖析每一个代码细节。</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Right Side: Forms (Main Content) */}
      <section className="flex-grow flex flex-col justify-center items-center p-gutter lg:p-xl bg-surface-container-low min-h-screen">
        <div className="max-w-[1000px] w-full py-8">
          {/* Mobile Branding */}
          <div className="lg:hidden flex flex-col items-center mb-8">
            <div className="flex items-center space-x-2 mb-2">
              <Icon name="school" className="material-symbols-outlined text-cyan-600" style={{ fontSize: '28px' }}/>
              <h2 className="font-['Plus_Jakarta_Sans',sans-serif] text-2xl font-bold text-slate-800">智能学习助手</h2>
            </div>
            <p className="text-xs text-slate-500 uppercase tracking-widest font-semibold">EduAgent Platform</p>
          </div>

          <div className="glass-panel p-gutter lg:p-xl rounded-2xl shadow-xl border border-surface-container-highest bg-white/80 backdrop-blur-md">
            {/* Tabs */}
            <div className="flex justify-center border-b border-surface-container-high mb-gutter">
              <Link to="/" className="px-xl py-sm font-h3 text-lg text-secondary hover:text-on-surface transition-colors">登入</Link>
              <button className="px-xl py-sm font-h3 text-lg text-primary border-b-4 border-primary font-bold">注册账号</button>
            </div>

            {/* Registration Form content */}
            <div className="max-w-[448px] mx-auto">
              <div className="text-center mb-gutter">
                <h3 className="font-h2 text-2xl text-on-surface font-bold">加入我们</h3>
                <p className="text-body-md text-secondary text-sm">开启您的个性化智能学习之旅</p>
              </div>

              {error && (
                <div className="flex items-center p-4 mb-4 text-error bg-error-container rounded-lg border border-error/20" role="alert">
                  <Icon name="error" className="material-symbols-outlined mr-2"/>
                  <span className="text-label-sm font-bold">{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-md text-left">
                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">用户名</label>
                  <input
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                    placeholder="设置您的登录用户名"
                    type="text"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    minLength={3}
                    maxLength={20}
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">真实姓名</label>
                  <input
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                    placeholder="输入您的真实姓名"
                    type="text"
                    name="fullName"
                    value={formData.fullName}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
                  <div className="space-y-xs">
                    <label className="text-label-sm text-secondary block font-medium text-xs">学号 / 工号</label>
                    <input
                      className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                      placeholder="输入学号或工号"
                      type="text"
                      name="studentId"
                      value={formData.studentId}
                      onChange={handleChange}
                    />
                  </div>
                  <div className="space-y-xs">
                    <label className="text-label-sm text-secondary block font-medium text-xs">专业</label>
                    <input
                      className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                      placeholder="例如：计算机科学"
                      type="text"
                      name="major"
                      value={formData.major}
                      onChange={handleChange}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-md">
                  <div className="space-y-xs">
                    <label className="text-label-sm text-secondary block font-medium text-xs">年级</label>
                    <select
                      className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                      name="grade"
                      value={formData.grade}
                      onChange={handleChange}
                    >
                      <option>大一 (Freshman)</option>
                      <option>大二 (Sophomore)</option>
                      <option>大三 (Junior)</option>
                      <option>大四 (Senior)</option>
                    </select>
                  </div>
                  <div className="space-y-xs">
                    <label className="text-label-sm text-secondary block font-medium text-xs">引导粒度</label>
                    <select
                      className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                      name="guidanceLevel"
                      value={formData.guidanceLevel}
                      onChange={handleChange}
                    >
                      <option value="L1">L1 - 自主学习 (最少干预)</option>
                      <option value="L2">L2 - 适度引导 (平衡干预)</option>
                      <option value="L3">L3 - 逐步指导 (最高干预)</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">电子邮箱</label>
                  <input
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                    placeholder="example@domain.com"
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">验证码 (Captcha)</label>
                  <div className="flex space-x-sm">
                    <div className="relative flex-grow">
                      <Icon name="verified_user" className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-sm"/>
                      <input
                        className="w-full pl-10 pr-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                        placeholder="输入计算结果"
                        type="text"
                        name="captchaCode"
                        value={formData.captchaCode || ''}
                        onChange={handleChange}
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

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">设置密码</label>
                  <input
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                    placeholder="至少8位字母与数字组合"
                    type="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">确认密码</label>
                  <input
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                    placeholder="再次输入密码"
                    type="password"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    required
                  />
                </div>

                <div className="space-y-xs">
                  <label className="text-label-sm text-secondary block font-medium text-xs">邀请码 <span className="text-error">*</span></label>
                  <input
                    className="w-full px-4 py-3 rounded-lg border border-outline-variant bg-surface-container-lowest focus:ring-2 focus:ring-primary outline-none transition-all"
                    placeholder="请输入您的邀请码"
                    required
                    type="text"
                    name="inviteCode"
                    value={formData.inviteCode}
                    onChange={handleChange}
                  />
                </div>

                <button
                  className="w-full py-4 bg-primary text-on-primary font-h3 rounded-lg shadow-md hover:brightness-110 active:scale-95 transition-all flex items-center justify-center space-x-2 text-lg font-bold disabled:opacity-70 disabled:cursor-not-allowed"
                  type="submit"
                  disabled={loading}
                >
                  <span>{loading ? '注册中...' : '完成注册'}</span>
                  {!loading && <Icon name="how_to_reg" className="material-symbols-outlined"/>}
                  {loading && <Icon name="refresh" className="material-symbols-outlined animate-spin"/>}
                </button>
              </form>

              <div className="text-center pt-md mt-gutter border-t border-surface-container-low">
                <p className="text-label-sm text-secondary text-xs">
                  已有账号? <Link to="/" className="text-primary font-bold hover:underline">立即登录</Link>
                </p>
              </div>
            </div>
          </div>

          {/* Footer Info */}
          <footer className="mt-xl text-center">
            <p className="text-label-sm text-outline mb-xs text-xs">© 2026 智能学习助手 (EduAgent). All rights reserved.</p>
            <div className="flex justify-center space-x-md text-label-sm text-secondary font-medium text-xs">
              <a className="hover:text-primary transition-colors" href="#">隐私政策</a>
              <a className="hover:text-primary transition-colors" href="#">服务条款</a>
            </div>
          </footer>
        </div>
      </section>
    </main>
  );
}
