import { useState, useEffect, useCallback } from 'react';
import { catalogService } from '../../api/services/catalog';
import CourseCatalogDrawer from './CourseCatalogDrawer';
import { getErrorMessage } from '../../utils/apiError';
import Icon from '../Icon';

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

export default function CatalogManagementPanel() {
  const [catalogs, setCatalogs] = useState([]);
  const [selectedCatalog, setSelectedCatalog] = useState(null);
  const [loadingCatalogs, setLoadingCatalogs] = useState(false);
  const [catalogError, setCatalogError] = useState('');
  const [newCatalogTitle, setNewCatalogTitle] = useState('');
  const [newCatalogDescription, setNewCatalogDescription] = useState('');
  const [creatingCatalog, setCreatingCatalog] = useState(false);

  const fetchCatalogs = useCallback(async () => {
    setLoadingCatalogs(true);
    setCatalogError('');
    try {
      const res = await catalogService.getCourseCatalogs();
      if (res.code === 200) {
        const nextCatalogs = res.data?.catalogs || [];
        setCatalogs(nextCatalogs);
        setSelectedCatalog((current) => {
          if (!current) return current;
          return nextCatalogs.find((catalog) => catalog.id === current.id) || current;
        });
      }
    } catch (e) {
      console.error(e);
      setCatalogError(getErrorMessage(e, '课程资源库加载失败'));
    } finally {
      setLoadingCatalogs(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCatalogs();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchCatalogs]);

  const handleCreateCatalog = async (event) => {
    event.preventDefault();
    const title = newCatalogTitle.trim();
    const description = newCatalogDescription.trim();
    if (!title || creatingCatalog) return;

    setCreatingCatalog(true);
    setCatalogError('');
    try {
      const res = await catalogService.createCourseCatalog({ title, description });
      if (res.code === 201 || res.code === 200) {
        setNewCatalogTitle('');
        setNewCatalogDescription('');
        await fetchCatalogs();
      } else {
        setCatalogError(res.message || '课程资源库创建失败');
      }
    } catch (e) {
      console.error(e);
      setCatalogError(getErrorMessage(e, '课程资源库创建失败'));
    } finally {
      setCreatingCatalog(false);
    }
  };

  const handleOpenCatalog = (catalog) => {
    setSelectedCatalog(catalog);
  };

  const handleCloseCatalog = () => {
    setSelectedCatalog(null);
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">课程资源库</h1>
          <p className="text-sm text-slate-500">维护平台共享课程内容资产，教师开班只能绑定已就绪资源库。</p>
        </div>
        <button onClick={fetchCatalogs} className="flex items-center gap-1 text-cyan-600 hover:underline text-sm font-medium cursor-pointer">
          <Icon name="refresh" className="material-symbols-outlined text-[18px]"/> 刷新资源库
        </button>
      </div>

      <form onSubmit={handleCreateCatalog} className="mb-6 bg-white border border-slate-200 rounded-xl shadow-sm p-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] lg:items-end">
          <label className="block">
            <span className="mb-1 block text-xs font-bold text-slate-500">资源库名称</span>
            <input
              type="text"
              value={newCatalogTitle}
              onChange={(e) => setNewCatalogTitle(e.target.value)}
              placeholder="输入资源库名称"
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition-all focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-bold text-slate-500">描述</span>
            <input
              type="text"
              value={newCatalogDescription}
              onChange={(e) => setNewCatalogDescription(e.target.value)}
              placeholder="输入资源库描述"
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition-all focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20"
            />
          </label>
          <button
            type="submit"
            disabled={!newCatalogTitle.trim() || creatingCatalog}
            className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              !newCatalogTitle.trim() || creatingCatalog
                ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
            }`}
          >
            <Icon name="add" className="material-symbols-outlined text-[18px]"/>
            {creatingCatalog ? '创建中' : '创建'}
          </button>
        </div>
      </form>

      {catalogError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {catalogError}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-500">
            <tr>
              <th className="px-6 py-4 font-medium">资源库</th>
              <th className="px-6 py-4 font-medium">状态</th>
              <th className="px-6 py-4 font-medium">资料数</th>
              <th className="px-6 py-4 font-medium">创建时间</th>
              <th className="px-6 py-4 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loadingCatalogs ? (
              <tr><td colSpan="5" className="text-center py-12 text-slate-400">加载中...</td></tr>
            ) : catalogs.length === 0 ? (
              <tr><td colSpan="5" className="text-center py-12 text-slate-400">暂无课程资源库</td></tr>
            ) : (
              catalogs.map((catalog) => (
                <tr
                  key={catalog.id}
                  onClick={() => handleOpenCatalog(catalog)}
                  className="cursor-pointer hover:bg-slate-50/50 transition-colors"
                >
                  <td className="px-6 py-4">
                    <div className="font-bold text-slate-900">{catalog.title || '未命名资源库'}</div>
                    <div className="mt-1 max-w-[576px] text-xs text-slate-500">{catalog.description || '暂无描述'}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">
                        {catalog.status || 'UNKNOWN'}
                      </span>
                      {catalog.knowledge_status && (
                        <span className="rounded bg-cyan-50 px-2.5 py-1 text-xs font-bold text-cyan-700">
                          {catalog.knowledge_status}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-slate-600">
                    {catalog.material_count ?? catalog.materials_count ?? catalog.materials?.length ?? '—'}
                  </td>
                  <td className="px-6 py-4 text-slate-500 text-xs">{formatDateTime(catalog.created_at)}</td>
                  <td className="px-6 py-4 text-right">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleOpenCatalog(catalog);
                      }}
                      className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-cyan-200 bg-white px-3 py-1.5 text-xs font-medium text-cyan-700 transition-colors hover:bg-cyan-50"
                    >
                      <Icon name="folder_managed" className="material-symbols-outlined text-[16px]"/>
                      管理资料
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <CourseCatalogDrawer
        catalog={selectedCatalog}
        open={Boolean(selectedCatalog)}
        onClose={handleCloseCatalog}
        onChanged={fetchCatalogs}
      />
    </div>
  );
}
