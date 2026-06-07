import { useEffect, useState } from 'react';
import { courseService } from '../api/services/course';

export default function CreateCourseDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [catalogs, setCatalogs] = useState([]);
  const [catalogsLoading, setCatalogsLoading] = useState(false);
  const [catalogId, setCatalogId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    const timer = setTimeout(() => {
      setCatalogsLoading(true);
      setError('');
      courseService.getReadyCatalogs()
        .then((res) => {
          if (cancelled) return;
          if (res.code !== 200) {
            throw new Error(res.message || '课程资源库加载失败');
          }
          const readyCatalogs = res.data?.catalogs || [];
          setCatalogs(readyCatalogs);
          setCatalogId(readyCatalogs[0]?.id || '');
        })
        .catch((err) => {
          if (cancelled) return;
          console.error('course catalogs fetch error', err);
          setCatalogs([]);
          setCatalogId('');
          setError('课程资源库加载失败，请联系管理员');
        })
        .finally(() => {
          if (!cancelled) setCatalogsLoading(false);
        });
    }, 0);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !catalogId) return;
    setSubmitting(true);
    setError('');

    try {
      const res = await courseService.createCourse({
        name: name.trim(),
        description: description.trim() || undefined,
        catalog_id: catalogId
      });
      if (res.code === 201) {
        setResult(res.data);
        if (onCreated) {
          await onCreated(res.data);
        }
      } else {
        setError(res.message || '创建失败');
      }
    } catch (err) {
      setError(
        err.response?.data?.detail?.message
          || err.response?.data?.message
          || '网络错误，请重试'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setDescription('');
    setCatalogs([]);
    setCatalogId('');
    setError('');
    setResult(null);
    setCopied(false);
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
      <div className="bg-white rounded-2xl shadow-xl p-6 w-[min(92vw,24rem)] min-w-[18rem] box-border mx-4">
        <h2 className="text-lg font-bold text-slate-900 mb-1 whitespace-nowrap">创建教学班</h2>
        <p className="text-sm text-slate-500 mb-4">选择共享课程资源库并开设教学班</p>

        {result ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50 rounded-lg p-3 text-sm font-medium">
              <span className="material-symbols-outlined text-lg">check_circle</span>
              教学班创建成功
            </div>
            <div className="bg-slate-50 rounded-lg p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">课程码</p>
              <p className="text-2xl font-bold text-cyan-700 tracking-wider font-mono">{result.course_code}</p>
              <p className="text-sm text-slate-600 mt-1">{result.name}</p>
              {result.catalog_title && (
                <p className="text-xs text-slate-500 mt-2 break-words">绑定资源库：{result.catalog_title}</p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={copyCode}
                className="flex-1 px-4 py-2 text-sm font-semibold text-cyan-600 bg-cyan-50 hover:bg-cyan-100 rounded-lg transition-colors"
              >
                <span className="whitespace-nowrap">{copied ? '已复制' : '复制课程码'}</span>
              </button>
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors"
              >
                <span className="whitespace-nowrap">完成</span>
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="space-y-3">
              <div>
                {catalogsLoading ? (
                  <div className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-500 bg-slate-50">
                    正在加载课程资源库...
                  </div>
                ) : catalogs.length === 0 ? (
                  <div className="w-full px-4 py-2.5 border border-amber-200 rounded-lg text-sm text-amber-700 bg-amber-50 break-words">
                    暂无可绑定课程资源库，请联系管理员先完成资料入库。
                  </div>
                ) : (
                  <select
                    value={catalogId}
                    onChange={(e) => setCatalogId(e.target.value)}
                    disabled={submitting}
                    className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
                  >
                    {catalogs.map((catalog) => (
                      <option key={catalog.id} value={catalog.id}>
                        {catalog.title}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <input
                autoFocus
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="教学班名称，如 数据结构2026春一班"
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
                <span className="whitespace-nowrap">取消</span>
              </button>
              <button
                type="submit"
                disabled={submitting || catalogsLoading || !name.trim() || !catalogId || catalogs.length === 0}
                className="px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="whitespace-nowrap">{submitting ? '创建中...' : '创建教学班'}</span>
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
