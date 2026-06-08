import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { adminService } from '../../api/services/admin';
import { taskService } from '../../api/services/task';
import { getErrorMessage } from '../../utils/apiError';

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const formatFileSize = (value) => {
  if (value === undefined || value === null) return '—';
  const size = Number(value);
  if (Number.isNaN(size)) return String(value);
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
};

const getBadgeClass = (status) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'ready' || normalized === 'completed' || normalized === 'uploaded') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  }
  if (normalized === 'ingesting' || normalized === 'processing' || normalized === 'dirty') {
    return 'bg-cyan-50 text-cyan-700 border-cyan-200';
  }
  if (normalized === 'failed' || normalized === 'partial') {
    return 'bg-red-50 text-red-700 border-red-200';
  }
  return 'bg-slate-100 text-slate-600 border-slate-200';
};

const normalizeTask = (task, fallbackId) => ({
  id: task?.id || task?.task_id || fallbackId || '',
  task_id: task?.task_id || fallbackId || '',
  task_type: task?.task_type || 'course_catalog_ingestion',
  status: task?.status || 'processing',
  progress: task?.progress ?? 0,
  error_message: task?.error_message || '',
  created_at: task?.created_at,
  completed_at: task?.completed_at
});

export default function CourseCatalogDrawer({ catalog, open, onClose, onChanged }) {
  const [materials, setMaterials] = useState([]);
  const [knowledgeStatus, setKnowledgeStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadQueue, setUploadQueue] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [taskError, setTaskError] = useState('');
  const requestSeqRef = useRef(0);
  const isMountedRef = useRef(false);

  const catalogId = catalog?.id;

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      requestSeqRef.current += 1;
    };
  }, []);

  const canWriteRequest = useCallback((requestSeq) => (
    isMountedRef.current && requestSeqRef.current === requestSeq
  ), []);

  const refreshDetails = useCallback(async () => {
    if (!catalogId || !open) return false;

    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError('');
    try {
      const [materialsRes, statusRes] = await Promise.all([
        adminService.getCourseCatalogMaterials(catalogId),
        adminService.getCourseCatalogStatus(catalogId)
      ]);
      if (!canWriteRequest(requestSeq)) return false;

      const incomingStatus = statusRes.data || null;
      setMaterials(materialsRes.data?.materials || []);
      setKnowledgeStatus(incomingStatus);

      const isIncomingIngesting = incomingStatus?.status === 'ingesting'
        || incomingStatus?.knowledge_status === 'ingesting';
      const incomingTaskId = incomingStatus?.last_ingestion_task_id;
      const incomingTaskStatus = incomingStatus?.last_ingestion_status || 'processing';
      const isTerminalTask = incomingTaskStatus === 'completed' || incomingTaskStatus === 'failed';

      if (isIncomingIngesting && incomingTaskId && !isTerminalTask) {
        setIngesting(true);
        setTaskError('');
        setActiveTask((prev) => {
          if (prev?.task_id === incomingTaskId && prev.status === 'processing') return prev;
          if (prev?.task_id === incomingTaskId && (prev.status === 'completed' || prev.status === 'failed')) return prev;
          return normalizeTask({
            id: incomingTaskId,
            task_id: incomingTaskId,
            status: 'processing',
            progress: 0
          }, incomingTaskId);
        });
      }
      return true;
    } catch (err) {
      console.error('course catalog drawer refresh error', err);
      if (!canWriteRequest(requestSeq)) return false;

      setError(getErrorMessage(err, '课程资源库详情加载失败'));
      setMaterials([]);
      setKnowledgeStatus(null);
      return false;
    } finally {
      if (canWriteRequest(requestSeq)) {
        setLoading(false);
      }
    }
  }, [canWriteRequest, catalogId, open]);

  useEffect(() => {
    if (!open || !catalogId) return;

    setMaterials([]);
    setKnowledgeStatus(null);
    setUploadQueue([]);
    setUploading(false);
    setIngesting(false);
    setActiveTask(null);
    setTaskError('');
    refreshDetails();

    return () => {
      requestSeqRef.current += 1;
    };
  }, [catalogId, open, refreshDetails]);

  useEffect(() => {
    if (!open || activeTask?.status !== 'processing' || !activeTask?.task_id) return;

    let cancelled = false;
    let timeoutId;

    const handleTerminalTask = async (task) => {
      if (cancelled) return;
      setIngesting(false);
      if (task.status === 'failed') {
        setTaskError(task.error_message || '课程资源库入库失败');
      }
      const refreshed = await refreshDetails();
      if (!cancelled && refreshed && onChanged) {
        onChanged();
      }
    };

    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(activeTask.task_id);
        if (cancelled) return;

        const task = normalizeTask(res.data, activeTask.task_id);
        setActiveTask(task);

        if (task.status === 'completed' || task.status === 'failed') {
          await handleTerminalTask(task);
        } else if (task.status === 'processing' && !cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('course catalog ingestion task poll error', err);
        const message = getErrorMessage(err, '入库任务状态查询失败');
        setTaskError(message);
        setIngesting(false);
        setActiveTask((prev) => ({
          ...normalizeTask(prev, activeTask.task_id),
          status: 'failed',
          error_message: message
        }));
        const refreshed = await refreshDetails();
        if (!cancelled && refreshed && onChanged) {
          onChanged();
        }
      }
    };

    timeoutId = setTimeout(pollTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [activeTask?.status, activeTask?.task_id, onChanged, open, refreshDetails]);

  const summary = useMemo(() => ({
    material_count: knowledgeStatus?.material_count ?? catalog?.material_count ?? catalog?.materials_count ?? materials.length,
    chunk_count: knowledgeStatus?.chunk_count ?? catalog?.chunk_count ?? 0,
    pending_material_count: knowledgeStatus?.pending_material_count ?? materials.filter((item) => item.status === 'uploaded').length,
    failed_material_count: knowledgeStatus?.failed_material_count ?? materials.filter((item) => item.status === 'failed').length
  }), [catalog, knowledgeStatus, materials]);

  const hasIngestibleMaterials = useMemo(
    () => materials.some((item) => item.status === 'uploaded' || item.status === 'failed'),
    [materials]
  );

  const catalogIngesting = catalog?.status === 'ingesting'
    || knowledgeStatus?.status === 'ingesting'
    || knowledgeStatus?.knowledge_status === 'ingesting';
  const taskProcessing = activeTask?.status === 'processing';
  const uploadDisabled = uploading || catalogIngesting || ingesting || taskProcessing;
  const startDisabled = catalogIngesting || uploading || !hasIngestibleMaterials || taskProcessing || ingesting;

  const handleUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!catalogId || files.length === 0 || uploadDisabled) return;

    const queuedFiles = files.map((file, index) => ({
      id: `${Date.now()}-${index}-${file.name}`,
      name: file.name,
      status: 'pending',
      message: ''
    }));

    setUploadQueue(queuedFiles);
    setUploading(true);
    setError('');

    for (const [index, item] of queuedFiles.entries()) {
      setUploadQueue((prev) => prev.map((queueItem) => (
        queueItem.id === item.id ? { ...queueItem, status: 'uploading', message: '' } : queueItem
      )));
      try {
        const res = await adminService.uploadCourseCatalogMaterial(catalogId, files[index]);
        setUploadQueue((prev) => prev.map((queueItem) => (
          queueItem.id === item.id
            ? { ...queueItem, status: 'completed', message: res.message || '上传完成' }
            : queueItem
        )));
      } catch (err) {
        console.error('course catalog material upload error', err);
        setUploadQueue((prev) => prev.map((queueItem) => (
          queueItem.id === item.id
            ? { ...queueItem, status: 'failed', message: getErrorMessage(err, '上传失败') }
            : queueItem
        )));
      }
    }

    setUploading(false);
    await refreshDetails();
    if (onChanged) {
      onChanged();
    }
  };

  const handleStartIngestion = async () => {
    if (!catalogId || startDisabled) return;

    setIngesting(true);
    setTaskError('');
    setError('');
    try {
      const res = await adminService.startCourseCatalogIngestion(catalogId);
      const task = normalizeTask(res.data);
      setActiveTask(task);
    } catch (err) {
      console.error('course catalog ingestion start error', err);
      setTaskError(getErrorMessage(err, '课程资源库入库启动失败'));
      setIngesting(false);
    }
  };

  if (!open || !catalog) return null;

  return (
    <div data-testid="catalog-drawer" className="fixed inset-0 z-50 flex justify-end bg-slate-900/35">
      <button
        type="button"
        aria-label="关闭资源库详情"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-[560px] flex-col bg-white shadow-2xl">
        <header className="border-b border-slate-200 px-6 py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="mb-1 text-xs font-bold text-slate-400">课程资源库详情</p>
              <h2 className="break-words text-xl font-bold text-slate-900">{catalog.title || '未命名资源库'}</h2>
              <p className="mt-1 break-words text-sm text-slate-500">{catalog.description || '暂无描述'}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
              title="关闭"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(knowledgeStatus?.status || catalog.status)}`}>
              资源库 {knowledgeStatus?.status || catalog.status || 'UNKNOWN'}
            </span>
            <span className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(knowledgeStatus?.knowledge_status || catalog.knowledge_status)}`}>
              知识库 {knowledgeStatus?.knowledge_status || catalog.knowledge_status || 'UNKNOWN'}
            </span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <section className="mb-5 grid grid-cols-2 gap-3">
            {[
              ['资料数', summary.material_count],
              ['知识切片', summary.chunk_count],
              ['待入库', summary.pending_material_count],
              ['失败资料', summary.failed_material_count]
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="text-xs font-bold text-slate-500">{label}</div>
                <div className="mt-1 text-2xl font-bold text-slate-900">{value ?? 0}</div>
              </div>
            ))}
          </section>

          <section className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">上传资料</h3>
                <p className="mt-1 text-xs text-slate-500">支持 TXT、Markdown、PDF 文件。</p>
              </div>
              <label className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                uploadDisabled
                  ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                  : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
              }`}>
                <span className="material-symbols-outlined text-[18px]">upload_file</span>
                {uploading ? '上传中' : '选择文件'}
                <input
                  data-testid="catalog-upload-input"
                  type="file"
                  accept=".txt,.md,.pdf"
                  multiple
                  disabled={uploadDisabled}
                  onChange={handleUpload}
                  className="hidden"
                />
              </label>
            </div>
            {uploadQueue.length > 0 && (
              <div className="mt-4 space-y-2">
                {uploadQueue.map((item) => (
                  <div key={item.id} className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <div className="break-words font-medium text-slate-800">{item.name}</div>
                      {item.message && <div className="mt-0.5 break-words text-xs text-slate-500">{item.message}</div>}
                    </div>
                    <span className={`flex-shrink-0 rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(item.status)}`}>
                      {item.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="mb-5 rounded-lg border border-slate-200 bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <h3 className="text-sm font-bold text-slate-900">资料列表</h3>
              {loading && <span className="text-xs text-slate-400">加载中...</span>}
            </div>
            <div className="max-h-72 overflow-y-auto">
              {materials.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-400">暂无资料</div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {materials.map((material) => (
                    <div key={material.id || material.filename} data-testid="catalog-material-row" className="px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="break-words text-sm font-semibold text-slate-900">{material.filename || '未命名资料'}</div>
                          <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                            <span>{material.source_type || 'file'}</span>
                            <span>{formatFileSize(material.file_size)}</span>
                            <span>切片 {material.chunk_count ?? 0}</span>
                            <span>创建 {formatDateTime(material.created_at)}</span>
                          </div>
                          {material.last_error && (
                            <div className="mt-2 break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                              {material.last_error}
                            </div>
                          )}
                        </div>
                        <span className={`flex-shrink-0 rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(material.status)}`}>
                          {material.status || 'UNKNOWN'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section data-testid="catalog-task-status" className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">入库任务</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {knowledgeStatus?.last_ingestion_task_id ? `最近任务 ${knowledgeStatus.last_ingestion_task_id}` : '暂无历史任务'}
                </p>
              </div>
              <button
                data-testid="catalog-start-ingestion"
                type="button"
                onClick={handleStartIngestion}
                disabled={startDisabled}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  startDisabled
                    ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                    : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
                }`}
              >
                <span className={`material-symbols-outlined text-[18px] ${taskProcessing ? 'animate-spin' : ''}`}>
                  {taskProcessing ? 'progress_activity' : 'play_arrow'}
                </span>
                {taskProcessing || ingesting ? '入库中' : '开始入库'}
              </button>
            </div>

            {activeTask ? (
              <div className="mt-4 space-y-2 rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-slate-500">task_id</span>
                  <span className="break-all font-mono text-xs text-slate-800">{activeTask.task_id || '—'}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-slate-500">status</span>
                  <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(activeTask.status)}`}>{activeTask.status || '—'}</span>
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-xs text-slate-500">
                    <span>progress</span>
                    <span>{activeTask.progress ?? 0}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-cyan-500 transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, activeTask.progress ?? 0))}%` }}
                    />
                  </div>
                </div>
                {(activeTask.error_message || taskError) && (
                  <div className="break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                    {activeTask.error_message || taskError}
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-4 rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-500">
                {taskError || knowledgeStatus?.last_error || '点击开始入库后将在此显示任务状态。'}
              </div>
            )}
          </section>
        </div>
      </aside>
    </div>
  );
}
