import { useState } from 'react';
import { courseService } from '../api/services/course';

export default function CreateCourseDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError('');

    try {
      const res = await courseService.createCourse({
        name: name.trim(),
        description: description.trim() || undefined
      });
      if (res.code === 201) {
        setResult(res.data);
        if (onCreated) {
          await onCreated(res.data);
        }
      } else {
        setError(res.message || '创建失败');
      }
    } catch {
      setError('网络错误，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setDescription('');
    setError('');
    setResult(null);
    onClose();
  };

  const copyCode = async () => {
    if (!result?.course_code) return;
    try {
      await navigator.clipboard.writeText(result.course_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for environments without clipboard API
      const el = document.createElement('textarea');
      el.value = result.course_code;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h2 className="text-lg font-bold text-slate-900 mb-1">创建课程</h2>
        <p className="text-sm text-slate-500 mb-4">开设一个新课程并获取课程码</p>

        {result ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50 rounded-lg p-3 text-sm font-medium">
              <span className="material-symbols-outlined text-lg">check_circle</span>
              课程创建成功
            </div>
            <div className="bg-slate-50 rounded-lg p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">课程码</p>
              <p className="text-2xl font-bold text-cyan-700 tracking-wider font-mono">{result.course_code}</p>
              <p className="text-sm text-slate-600 mt-1">{result.name}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={copyCode}
                className="flex-1 px-4 py-2 text-sm font-semibold text-cyan-600 bg-cyan-50 hover:bg-cyan-100 rounded-lg transition-colors"
              >
                {copied ? '已复制' : '复制课程码'}
              </button>
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors"
              >
                完成
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="space-y-3">
              <input
                autoFocus
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="课程名称，如 数据结构2026春"
                disabled={submitting}
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
              />
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="课程描述（可选）"
                disabled={submitting}
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
              />
            </div>
            {error && (
              <p className="mt-2 text-xs text-red-500">{error}</p>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={handleClose}
                disabled={submitting}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={submitting || !name.trim()}
                className="px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? '创建中...' : '创建'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
