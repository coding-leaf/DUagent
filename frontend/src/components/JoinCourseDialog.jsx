import { useState } from 'react';
import { courseService } from '../api/services/course';
import Icon from './Icon';

export default function JoinCourseDialog({ open, onClose, onJoined }) {
  const [courseCode, setCourseCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!courseCode.trim()) return;
    setSubmitting(true);
    setError('');
    setSuccess(false);

    try {
      const res = await courseService.joinCourse(courseCode.trim());
      if (res.code === 200) {
        setSuccess(true);
        if (onJoined) {
          await onJoined(res.data);
        }
        setTimeout(() => {
          onClose();
          setCourseCode('');
          setSuccess(false);
        }, 1500);
      } else {
        setError(res.message || '加入失败，请检查课程码');
      }
    } catch {
      setError('网络错误，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-[min(92vw,24rem)] min-w-[18rem] box-border mx-4">
        <h2 className="text-lg font-bold text-slate-900 mb-1 whitespace-nowrap">加入课程</h2>
        <p className="text-sm text-slate-500 mb-4">输入教师提供的课程码加入课程</p>

        {success ? (
          <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50 rounded-lg p-3 text-sm font-medium">
            <Icon name="check_circle" className="material-symbols-outlined text-lg"/>
            加入成功
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <input
              autoFocus
              type="text"
              value={courseCode}
              onChange={(e) => setCourseCode(e.target.value)}
              placeholder="输入课程码，如 DS2026"
              disabled={submitting}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
            />
            {error && (
              <p className="mt-2 text-xs text-red-500">{error}</p>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              >
                <span className="whitespace-nowrap">取消</span>
              </button>
              <button
                type="submit"
                disabled={submitting || !courseCode.trim()}
                className="px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="whitespace-nowrap">{submitting ? '加入中...' : '加入'}</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
