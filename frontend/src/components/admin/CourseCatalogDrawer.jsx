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
  if (normalized === 'ready' || normalized === 'completed' || normalized === 'uploaded' || normalized === 'ingested') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  }
  if (normalized === 'ingesting' || normalized === 'processing' || normalized === 'dirty' || normalized === 'uploading') {
    return 'bg-cyan-50 text-cyan-700 border-cyan-200';
  }
  if (normalized === 'partial') {
    return 'bg-amber-50 text-amber-700 border-amber-200';
  }
  if (normalized === 'failed') {
    return 'bg-red-50 text-red-700 border-red-200';
  }
  return 'bg-slate-100 text-slate-600 border-slate-200';
};

const createStatusLabelFormatter = (labels, fallback) => (status) => {
  if (!status) return fallback;
  const normalized = String(status).toLowerCase();
  return labels[normalized] || status;
};

const formatCatalogStatus = createStatusLabelFormatter({
  draft: '未入库',
  ingesting: '入库中',
  ready: '可绑定',
  failed: '入库失败'
}, 'UNKNOWN');

const formatKnowledgeStatus = createStatusLabelFormatter({
  draft: '未入库',
  ingesting: '入库中',
  ready: '已同步',
  dirty: '待更新',
  partial: '部分失败',
  failed: '入库失败'
}, 'UNKNOWN');

const formatMaterialStatus = createStatusLabelFormatter({
  uploaded: '已上传',
  ingesting: '入库中',
  ingested: '已入库',
  failed: '入库失败'
}, 'UNKNOWN');

const formatUploadQueueStatus = createStatusLabelFormatter({
  queued: '等待上传',
  uploading: '上传中',
  uploaded: '已上传',
  failed: '上传失败'
}, 'UNKNOWN');

const formatTaskStatus = createStatusLabelFormatter({
  processing: '处理中',
  completed: '已完成',
  failed: '失败'
}, '—');

const formatResourceType = createStatusLabelFormatter({
  document: '文档',
  mindmap: '思维导图',
  reading: '阅读材料',
  code: '代码示例'
}, 'UNKNOWN');

const RESOURCE_TYPE_OPTIONS = [
  { value: 'document', label: '文档' },
  { value: 'mindmap', label: '思维导图' },
  { value: 'reading', label: '阅读材料' },
  { value: 'code', label: '代码示例' }
];

const createGenerationForm = () => ({
  chapter: '',
  knowledge_point: '',
  resource_types: []
});

const normalizeTask = (task, fallbackId, fallbackType = 'course_catalog_ingestion') => ({
  id: task?.id || task?.task_id || fallbackId || '',
  task_id: task?.task_id || fallbackId || '',
  task_type: task?.task_type || fallbackType,
  status: task?.status || 'processing',
  progress: task?.progress ?? 0,
  error_message: task?.error_message || '',
  created_at: task?.created_at,
  completed_at: task?.completed_at
});

export default function CourseCatalogDrawer({ catalog, open, onClose, onChanged }) {
  const [materials, setMaterials] = useState([]);
  const [resources, setResources] = useState([]);
  const [knowledgeStatus, setKnowledgeStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadQueue, setUploadQueue] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [activeTask, setActiveTask] = useState(null);
  const [taskError, setTaskError] = useState('');
  const [generationForm, setGenerationForm] = useState(createGenerationForm);
  const [generating, setGenerating] = useState(false);
  const [generationTask, setGenerationTask] = useState(null);
  const [generationTaskError, setGenerationTaskError] = useState('');
  const [knowledgeGraphStatus, setKnowledgeGraphStatus] = useState(null);
  const [knowledgeGraphGenerating, setKnowledgeGraphGenerating] = useState(false);
  const [knowledgeGraphTask, setKnowledgeGraphTask] = useState(null);
  const [knowledgeGraphTaskError, setKnowledgeGraphTaskError] = useState('');
  const [deletingMaterialIds, setDeletingMaterialIds] = useState(() => new Set());
  const [deletingResourceIds, setDeletingResourceIds] = useState(() => new Set());
  const requestSeqRef = useRef(0);
  const isMountedRef = useRef(false);
  const activeTaskRef = useRef(null);
  const generationTaskRef = useRef(null);
  const knowledgeGraphTaskRef = useRef(null);
  const catalogIdRef = useRef(null);
  const openRef = useRef(false);
  const uploadOperationSeqRef = useRef(0);
  const ingestionOperationSeqRef = useRef(0);
  const generationOperationSeqRef = useRef(0);
  const knowledgeGraphOperationSeqRef = useRef(0);
  const authoritativeTerminalTaskIdsRef = useRef(new Set());

  const catalogId = catalog?.id;

  useEffect(() => {
    activeTaskRef.current = activeTask;
  }, [activeTask]);

  useEffect(() => {
    generationTaskRef.current = generationTask;
  }, [generationTask]);

  useEffect(() => {
    knowledgeGraphTaskRef.current = knowledgeGraphTask;
  }, [knowledgeGraphTask]);

  useEffect(() => {
    catalogIdRef.current = catalogId;
    openRef.current = open;
  }, [catalogId, open]);

  useEffect(() => {
    isMountedRef.current = true;
    const authoritativeTerminalTaskIds = authoritativeTerminalTaskIdsRef.current;
    return () => {
      isMountedRef.current = false;
      requestSeqRef.current += 1;
      uploadOperationSeqRef.current += 1;
      ingestionOperationSeqRef.current += 1;
      generationOperationSeqRef.current += 1;
      knowledgeGraphOperationSeqRef.current += 1;
      authoritativeTerminalTaskIds.clear();
    };
  }, []);

  const canWriteRequest = useCallback((requestSeq) => (
    isMountedRef.current && requestSeqRef.current === requestSeq
  ), []);

  const canWriteUploadOperation = useCallback((operationSeq, operationCatalogId) => (
    isMountedRef.current
    && openRef.current
    && catalogIdRef.current === operationCatalogId
    && uploadOperationSeqRef.current === operationSeq
  ), []);

  const canWriteIngestionOperation = useCallback((operationSeq, operationCatalogId) => (
    isMountedRef.current
    && openRef.current
    && catalogIdRef.current === operationCatalogId
    && ingestionOperationSeqRef.current === operationSeq
  ), []);

  const canWriteGenerationOperation = useCallback((operationSeq, operationCatalogId) => (
    isMountedRef.current
    && openRef.current
    && catalogIdRef.current === operationCatalogId
    && generationOperationSeqRef.current === operationSeq
  ), []);

  const canWriteKnowledgeGraphOperation = useCallback((operationSeq, operationCatalogId) => (
    isMountedRef.current
    && openRef.current
    && catalogIdRef.current === operationCatalogId
    && knowledgeGraphOperationSeqRef.current === operationSeq
  ), []);

  const refreshDetails = useCallback(async () => {
    if (!catalogId || !open) return false;

    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError('');
    try {
      const [materialsRes, statusRes, resourcesRes, knowledgeGraphRes] = await Promise.all([
        adminService.getCourseCatalogMaterials(catalogId),
        adminService.getCourseCatalogStatus(catalogId),
        adminService.getCourseCatalogResources(catalogId, { page: 1, page_size: 50 }),
        adminService.getCourseCatalogKnowledgeGraphStatus(catalogId)
      ]);
      if (!canWriteRequest(requestSeq)) return false;

      const incomingStatus = statusRes.data || null;
      const incomingKnowledgeGraphStatus = knowledgeGraphRes.data || null;
      setMaterials(materialsRes.data?.materials || []);
      setResources(resourcesRes.data?.resources || []);
      setKnowledgeStatus(incomingStatus);
      setKnowledgeGraphStatus(incomingKnowledgeGraphStatus);

      const isIncomingIngesting = incomingStatus?.status === 'ingesting'
        || incomingStatus?.knowledge_status === 'ingesting';
      const incomingTaskId = incomingStatus?.last_ingestion_task_id;
      const incomingTaskStatus = incomingStatus?.last_ingestion_status || 'processing';
      const isTerminalTask = incomingTaskStatus === 'completed' || incomingTaskStatus === 'failed';
      const currentTask = activeTaskRef.current;
      const isCurrentTaskTerminal = currentTask?.task_id === incomingTaskId
        && (currentTask.status === 'completed' || currentTask.status === 'failed');

      if (isCurrentTaskTerminal) {
        setIngesting(false);
      } else if (isIncomingIngesting && incomingTaskId && !isTerminalTask) {
        setActiveTask((prev) => {
          if (prev?.task_id === incomingTaskId && prev.status === 'processing') return prev;
          if (prev?.task_id === incomingTaskId && (prev.status === 'completed' || prev.status === 'failed')) {
            setIngesting(false);
            return prev;
          }
          setIngesting(true);
          setTaskError('');
          return normalizeTask({
            id: incomingTaskId,
            task_id: incomingTaskId,
            status: 'processing',
            progress: 0
          }, incomingTaskId);
        });
      }

      const incomingKgTask = incomingKnowledgeGraphStatus?.last_generation_task;
      if (incomingKgTask?.task_id && incomingKgTask.status === 'processing') {
        setKnowledgeGraphTask((prev) => {
          if (prev?.task_id === incomingKgTask.task_id && prev.status === 'processing') return prev;
          setKnowledgeGraphGenerating(true);
          setKnowledgeGraphTaskError('');
          return normalizeTask(incomingKgTask, incomingKgTask.task_id, 'kg_generation');
        });
      }
      return true;
    } catch (err) {
      console.error('course catalog drawer refresh error', err);
      if (!canWriteRequest(requestSeq)) return false;

      setError(getErrorMessage(err, '课程资源库详情加载失败'));
      setMaterials([]);
      setResources([]);
      setKnowledgeStatus(null);
      setKnowledgeGraphStatus(null);
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
    setResources([]);
    setKnowledgeStatus(null);
    setUploadQueue([]);
    setUploading(false);
    setIngesting(false);
    setGenerating(false);
    setGenerationForm(createGenerationForm());
    setKnowledgeGraphStatus(null);
    setKnowledgeGraphGenerating(false);
    activeTaskRef.current = null;
    generationTaskRef.current = null;
    knowledgeGraphTaskRef.current = null;
    authoritativeTerminalTaskIdsRef.current.clear();
    setActiveTask(null);
    setTaskError('');
    setGenerationTask(null);
    setGenerationTaskError('');
    setKnowledgeGraphTask(null);
    setKnowledgeGraphTaskError('');
    setDeletingMaterialIds(new Set());
    setDeletingResourceIds(new Set());
    refreshDetails();

    const authoritativeTerminalTaskIds = authoritativeTerminalTaskIdsRef.current;
    return () => {
      requestSeqRef.current += 1;
      uploadOperationSeqRef.current += 1;
      ingestionOperationSeqRef.current += 1;
      generationOperationSeqRef.current += 1;
      knowledgeGraphOperationSeqRef.current += 1;
      authoritativeTerminalTaskIds.clear();
    };
  }, [catalogId, open, refreshDetails]);

  useEffect(() => {
    if (
      !open
      || !activeTask?.task_id
      || activeTask.status === 'completed'
      || activeTask.status === 'failed'
    ) return;

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
        activeTaskRef.current = task;
        setActiveTask(task);
        setTaskError('');

        if (task.status === 'completed' || task.status === 'failed') {
          authoritativeTerminalTaskIdsRef.current.add(task.task_id);
          await handleTerminalTask(task);
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('course catalog ingestion task poll error', err);
        const detail = getErrorMessage(err, '');
        setTaskError(detail ? `任务状态查询失败：${detail}，正在重试` : '任务状态查询失败，正在重试');
        if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      }
    };

    timeoutId = setTimeout(pollTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [activeTask?.status, activeTask?.task_id, onChanged, open, refreshDetails]);

  useEffect(() => {
    if (
      !open
      || !generationTask?.task_id
      || generationTask.status === 'completed'
      || generationTask.status === 'failed'
    ) return;

    let cancelled = false;
    let timeoutId;

    const handleTerminalTask = async (task) => {
      if (cancelled) return;
      setGenerating(false);
      if (task.status === 'failed') {
        setGenerationTaskError(task.error_message || '学习资源生成失败');
      }
      const refreshed = await refreshDetails();
      if (!cancelled && refreshed && onChanged) {
        onChanged();
      }
    };

    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(generationTask.task_id);
        if (cancelled) return;

        const task = normalizeTask(res.data, generationTask.task_id, 'resource_generation');
        generationTaskRef.current = task;
        setGenerationTask(task);
        setGenerationTaskError('');

        if (task.status === 'completed' || task.status === 'failed') {
          await handleTerminalTask(task);
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('course catalog resource generation task poll error', err);
        const detail = getErrorMessage(err, '');
        setGenerationTaskError(detail ? `生成任务状态查询失败：${detail}，正在重试` : '生成任务状态查询失败，正在重试');
        if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      }
    };

    timeoutId = setTimeout(pollTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [generationTask?.status, generationTask?.task_id, onChanged, open, refreshDetails]);

  useEffect(() => {
    if (
      !open
      || !knowledgeGraphTask?.task_id
      || knowledgeGraphTask.status === 'completed'
      || knowledgeGraphTask.status === 'failed'
    ) return;

    let cancelled = false;
    let timeoutId;

    const handleTerminalTask = async (task) => {
      if (cancelled) return;
      setKnowledgeGraphGenerating(false);
      if (task.status === 'failed') {
        setKnowledgeGraphTaskError(task.error_message || '知识图谱生成失败');
      }
      const refreshed = await refreshDetails();
      if (!cancelled && refreshed && onChanged) {
        onChanged();
      }
    };

    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(knowledgeGraphTask.task_id);
        if (cancelled) return;

        const task = normalizeTask(res.data, knowledgeGraphTask.task_id, 'kg_generation');
        knowledgeGraphTaskRef.current = task;
        setKnowledgeGraphTask(task);
        setKnowledgeGraphTaskError('');

        if (task.status === 'completed' || task.status === 'failed') {
          await handleTerminalTask(task);
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('course catalog knowledge graph generation task poll error', err);
        const detail = getErrorMessage(err, '');
        setKnowledgeGraphTaskError(detail ? `图谱任务状态查询失败：${detail}，正在重试` : '图谱任务状态查询失败，正在重试');
        if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      }
    };

    timeoutId = setTimeout(pollTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [knowledgeGraphTask?.status, knowledgeGraphTask?.task_id, onChanged, open, refreshDetails]);

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

  const taskProcessing = activeTask?.status === 'processing';
  const taskTerminal = activeTask?.status === 'completed' || activeTask?.status === 'failed';
  const generationProcessing = generationTask?.status === 'processing';
  const knowledgeGraphProcessing = knowledgeGraphTask?.status === 'processing'
    || knowledgeGraphStatus?.last_generation_task?.status === 'processing';
  const sameTerminalKnowledgeTask = taskTerminal
    && activeTask?.task_id
    && activeTask.task_id === knowledgeStatus?.last_ingestion_task_id
    && authoritativeTerminalTaskIdsRef.current.has(activeTask.task_id);
  const catalogIngesting = !sameTerminalKnowledgeTask && (
    catalog?.status === 'ingesting'
    || knowledgeStatus?.status === 'ingesting'
    || knowledgeStatus?.knowledge_status === 'ingesting'
  );
  const uploadDisabled = uploading || catalogIngesting || ingesting || taskProcessing || generationProcessing || generating || knowledgeGraphProcessing || knowledgeGraphGenerating;
  const startDisabled = catalogIngesting || uploading || !hasIngestibleMaterials || taskProcessing || ingesting || generationProcessing || generating || knowledgeGraphProcessing || knowledgeGraphGenerating;
  const knowledgeReadyStatus = knowledgeStatus?.knowledge_status || catalog?.knowledge_status;
  const hasReadyKnowledge = (knowledgeStatus?.status || catalog?.status) === 'ready'
    && (knowledgeReadyStatus === 'ready' || knowledgeReadyStatus === 'partial')
    && summary.chunk_count > 0;
  const hasActiveKnowledgeGraph = Boolean(knowledgeGraphStatus?.active_graph);
  const hasExplicitResourceTarget = Boolean(
    generationForm.chapter.trim() || generationForm.knowledge_point.trim()
  );
  const generationDisabled = !hasReadyKnowledge
    || (!hasActiveKnowledgeGraph && !hasExplicitResourceTarget)
    || generationForm.resource_types.length === 0
    || generationProcessing
    || generating
    || catalogIngesting
    || uploading
    || ingesting
    || taskProcessing
    || knowledgeGraphProcessing
    || knowledgeGraphGenerating;
  const materialDeleteDisabled = uploading || catalogIngesting || ingesting || taskProcessing || generationProcessing || generating || knowledgeGraphProcessing || knowledgeGraphGenerating;
  const resourceDeleteDisabled = generationProcessing || generating;
  const knowledgeGraphGenerationDisabled = knowledgeGraphProcessing
    || knowledgeGraphGenerating
    || !hasReadyKnowledge
    || catalogIngesting
    || uploading
    || ingesting
    || taskProcessing
    || generationProcessing
    || generating;

  const handleUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!catalogId || files.length === 0 || uploadDisabled) return;

    const operationCatalogId = catalogId;
    const operationSeq = uploadOperationSeqRef.current + 1;
    uploadOperationSeqRef.current = operationSeq;
    const queuedFiles = files.map((file, index) => ({
      id: `${Date.now()}-${index}-${file.name}`,
      name: file.name,
      status: 'queued',
      message: ''
    }));

    if (!canWriteUploadOperation(operationSeq, operationCatalogId)) return;
    setUploadQueue(queuedFiles);
    setUploading(true);
    setError('');

    for (const [index, item] of queuedFiles.entries()) {
      if (!canWriteUploadOperation(operationSeq, operationCatalogId)) return;
      setUploadQueue((prev) => prev.map((queueItem) => (
        queueItem.id === item.id ? { ...queueItem, status: 'uploading', message: '' } : queueItem
      )));
      try {
        const res = await adminService.uploadCourseCatalogMaterial(operationCatalogId, files[index]);
        if (!canWriteUploadOperation(operationSeq, operationCatalogId)) return;
        setUploadQueue((prev) => prev.map((queueItem) => (
          queueItem.id === item.id
            ? { ...queueItem, status: 'uploaded', message: res.message || '上传完成' }
            : queueItem
        )));
      } catch (err) {
        console.error('course catalog material upload error', err);
        if (!canWriteUploadOperation(operationSeq, operationCatalogId)) return;
        setUploadQueue((prev) => prev.map((queueItem) => (
          queueItem.id === item.id
            ? { ...queueItem, status: 'failed', message: getErrorMessage(err, '上传失败') }
            : queueItem
        )));
      }
    }

    if (!canWriteUploadOperation(operationSeq, operationCatalogId)) return;
    setUploading(false);
    const refreshed = await refreshDetails();
    if (canWriteUploadOperation(operationSeq, operationCatalogId) && refreshed && onChanged) {
      onChanged();
    }
  };

  const handleStartIngestion = async () => {
    if (!catalogId || startDisabled) return;

    const operationCatalogId = catalogId;
    const operationSeq = ingestionOperationSeqRef.current + 1;
    ingestionOperationSeqRef.current = operationSeq;
    if (!canWriteIngestionOperation(operationSeq, operationCatalogId)) return;
    setIngesting(true);
    setTaskError('');
    setError('');
    authoritativeTerminalTaskIdsRef.current.clear();
    try {
      const res = await adminService.startCourseCatalogIngestion(operationCatalogId);
      if (!canWriteIngestionOperation(operationSeq, operationCatalogId)) return;
      const task = normalizeTask(res.data);
      activeTaskRef.current = task;
      setActiveTask(task);
    } catch (err) {
      console.error('course catalog ingestion start error', err);
      if (!canWriteIngestionOperation(operationSeq, operationCatalogId)) return;
      setTaskError(getErrorMessage(err, '课程资源库入库启动失败'));
      setIngesting(false);
    }
  };

  const handleGenerationFieldChange = (field, value) => {
    setGenerationForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleGenerationTypeToggle = (type) => {
    setGenerationForm((prev) => {
      const exists = prev.resource_types.includes(type);
      return {
        ...prev,
        resource_types: exists
          ? prev.resource_types.filter((item) => item !== type)
          : [...prev.resource_types, type]
      };
    });
  };

  const handleStartKnowledgeGraphGeneration = async () => {
    if (!catalogId || knowledgeGraphGenerationDisabled) return;

    const operationCatalogId = catalogId;
    const operationSeq = knowledgeGraphOperationSeqRef.current + 1;
    knowledgeGraphOperationSeqRef.current = operationSeq;
    if (!canWriteKnowledgeGraphOperation(operationSeq, operationCatalogId)) return;

    setKnowledgeGraphGenerating(true);
    setKnowledgeGraphTaskError('');
    setError('');
    try {
      const res = await adminService.startCourseCatalogKnowledgeGraphGeneration(operationCatalogId);
      if (!canWriteKnowledgeGraphOperation(operationSeq, operationCatalogId)) return;
      const task = normalizeTask(res.data, res.data?.task_id, 'kg_generation');
      knowledgeGraphTaskRef.current = task;
      setKnowledgeGraphTask(task);
    } catch (err) {
      console.error('course catalog knowledge graph generation start error', err);
      if (!canWriteKnowledgeGraphOperation(operationSeq, operationCatalogId)) return;
      setKnowledgeGraphTaskError(getErrorMessage(err, '知识图谱生成启动失败'));
      setKnowledgeGraphGenerating(false);
    }
  };

  const handleStartGeneration = async () => {
    if (!catalogId || generationDisabled) return;

    const operationCatalogId = catalogId;
    const operationSeq = generationOperationSeqRef.current + 1;
    generationOperationSeqRef.current = operationSeq;
    if (!canWriteGenerationOperation(operationSeq, operationCatalogId)) return;

    setGenerating(true);
    setGenerationTaskError('');
    setError('');
    try {
      const payload = {
        chapter: generationForm.chapter.trim(),
        knowledge_point: generationForm.knowledge_point.trim(),
        resource_types: generationForm.resource_types
      };
      const res = await adminService.startCourseCatalogResourceGeneration(operationCatalogId, payload);
      if (!canWriteGenerationOperation(operationSeq, operationCatalogId)) return;
      const task = normalizeTask(res.data, res.data?.task_id, 'resource_generation');
      generationTaskRef.current = task;
      setGenerationTask(task);
    } catch (err) {
      console.error('course catalog resource generation start error', err);
      if (!canWriteGenerationOperation(operationSeq, operationCatalogId)) return;
      setGenerationTaskError(getErrorMessage(err, '学习资源生成启动失败'));
      setGenerating(false);
    }
  };

  const handleDeleteMaterial = async (material) => {
    if (!catalogId || !material?.id || materialDeleteDisabled || deletingMaterialIds.has(material.id)) return;

    setDeletingMaterialIds((prev) => new Set(prev).add(material.id));
    setError('');
    try {
      const res = await adminService.deleteCourseCatalogMaterial(catalogId, material.id);
      setMaterials((prev) => prev.filter((item) => item.id !== material.id));
      if (res.data?.knowledge_status) {
        setKnowledgeStatus((prev) => ({
          ...(prev || {}),
          catalog_id: catalogId,
          knowledge_status: res.data.knowledge_status,
          material_count: Math.max(0, (prev?.material_count ?? materials.length) - 1)
        }));
      }
      const refreshed = await refreshDetails();
      if (refreshed && onChanged) onChanged();
    } catch (err) {
      console.error('course catalog material delete error', err);
      setError(getErrorMessage(err, '资料删除失败'));
    } finally {
      setDeletingMaterialIds((prev) => {
        const next = new Set(prev);
        next.delete(material.id);
        return next;
      });
    }
  };

  const handleDeleteResource = async (resource) => {
    if (!resource?.id || resourceDeleteDisabled || deletingResourceIds.has(resource.id)) return;

    setDeletingResourceIds((prev) => new Set(prev).add(resource.id));
    setError('');
    try {
      await adminService.deleteResource(resource.id);
      setResources((prev) => prev.filter((item) => item.id !== resource.id));
      await refreshDetails();
    } catch (err) {
      console.error('course catalog generated resource delete error', err);
      setError(getErrorMessage(err, '资源删除失败'));
    } finally {
      setDeletingResourceIds((prev) => {
        const next = new Set(prev);
        next.delete(resource.id);
        return next;
      });
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
              资源库 {formatCatalogStatus(knowledgeStatus?.status || catalog.status)}
            </span>
            <span className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(knowledgeStatus?.knowledge_status || catalog.knowledge_status)}`}>
              知识库 {formatKnowledgeStatus(knowledgeStatus?.knowledge_status || catalog.knowledge_status)}
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
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">知识图谱</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {knowledgeGraphStatus?.course_id ? `绑定教学班 ${knowledgeGraphStatus.course_id}` : '尚未绑定教学班'}
                </p>
              </div>
              <button
                data-testid="catalog-start-kg-generation"
                type="button"
                onClick={handleStartKnowledgeGraphGeneration}
                disabled={knowledgeGraphGenerationDisabled}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  knowledgeGraphGenerationDisabled
                    ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                    : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
                }`}
              >
                <span className={`material-symbols-outlined text-[18px] ${knowledgeGraphProcessing ? 'animate-spin' : ''}`}>
                  {knowledgeGraphProcessing ? 'progress_activity' : 'account_tree'}
                </span>
                {knowledgeGraphProcessing || knowledgeGraphGenerating ? '刷新中' : '刷新图谱'}
              </button>
            </div>

            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
              {knowledgeGraphStatus?.active_graph ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs font-bold text-slate-500">当前版本</div>
                    <div className="mt-1 font-semibold text-slate-900">v{knowledgeGraphStatus.active_graph.version}</div>
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-500">节点 / 边</div>
                    <div className="mt-1 font-semibold text-slate-900">
                      {knowledgeGraphStatus.active_graph.node_count ?? 0} / {knowledgeGraphStatus.active_graph.edge_count ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-500">来源</div>
                    <div className="mt-1 font-semibold text-slate-900">{knowledgeGraphStatus.active_graph.source_type || '—'}</div>
                  </div>
                  <div>
                    <div className="text-xs font-bold text-slate-500">创建时间</div>
                    <div className="mt-1 font-semibold text-slate-900">{formatDateTime(knowledgeGraphStatus.active_graph.created_at)}</div>
                  </div>
                </div>
              ) : (
                <div className="text-slate-500">暂无 active 知识图谱。</div>
              )}
            </div>

            <div data-testid="catalog-kg-task-status" className="mt-4">
              {knowledgeGraphTask ? (
                <div className="space-y-2 rounded-lg bg-slate-50 p-3 text-sm">
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-500">task_id</span>
                    <span className="break-all font-mono text-xs text-slate-800">{knowledgeGraphTask.task_id || '—'}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-500">status</span>
                    <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(knowledgeGraphTask.status)}`}>
                      {formatTaskStatus(knowledgeGraphTask.status)}
                    </span>
                  </div>
                  <div>
                    <div className="mb-1 flex justify-between text-xs text-slate-500">
                      <span>progress</span>
                      <span>{knowledgeGraphTask.progress ?? 0}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-cyan-500 transition-all"
                        style={{ width: `${Math.max(0, Math.min(100, knowledgeGraphTask.progress ?? 0))}%` }}
                      />
                    </div>
                  </div>
                  {(knowledgeGraphTask.error_message || knowledgeGraphTaskError) && (
                    <div className="break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                      {knowledgeGraphTask.error_message || knowledgeGraphTaskError}
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-500">
                  {knowledgeGraphTaskError
                    || (knowledgeGraphStatus?.last_generation_task?.task_id
                      ? `最近图谱任务 ${knowledgeGraphStatus.last_generation_task.task_id}`
                      : '知识库就绪后可根据已入库切片刷新 active 图谱。')}
                </div>
              )}
            </div>
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
                      {formatUploadQueueStatus(item.status)}
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
                        <div className="flex flex-shrink-0 items-center gap-2">
                          <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(material.status)}`}>
                            {formatMaterialStatus(material.status)}
                          </span>
                          <button
                            type="button"
                            aria-label="删除资料"
                            title="删除资料"
                            disabled={materialDeleteDisabled || deletingMaterialIds.has(material.id) || !material.id}
                            onClick={() => handleDeleteMaterial(material)}
                            className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                              materialDeleteDisabled || deletingMaterialIds.has(material.id) || !material.id
                                ? 'cursor-not-allowed text-slate-300'
                                : 'text-red-500 hover:bg-red-50 hover:text-red-700'
                            }`}
                          >
                            <span className="material-symbols-outlined text-[18px]">
                              {deletingMaterialIds.has(material.id) ? 'progress_activity' : 'delete'}
                            </span>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">生成学习资源</h3>
                <p className="mt-1 text-xs text-slate-500">基于已入库知识为当前绑定教学班生成资源。</p>
              </div>
              <button
                type="button"
                onClick={handleStartGeneration}
                disabled={generationDisabled}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  generationDisabled
                    ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                    : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
                }`}
              >
                <span className={`material-symbols-outlined text-[18px] ${generationProcessing ? 'animate-spin' : ''}`}>
                  {generationProcessing ? 'progress_activity' : 'auto_awesome'}
                </span>
                {generationProcessing || generating ? '生成中' : '生成资源'}
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                type="text"
                placeholder="章节"
                value={generationForm.chapter}
                onChange={(event) => handleGenerationFieldChange('chapter', event.target.value)}
                disabled={generationProcessing || generating}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none transition-colors focus:border-cyan-500 disabled:bg-slate-50 disabled:text-slate-400"
              />
              <input
                type="text"
                placeholder="知识点"
                value={generationForm.knowledge_point}
                onChange={(event) => handleGenerationFieldChange('knowledge_point', event.target.value)}
                disabled={generationProcessing || generating}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none transition-colors focus:border-cyan-500 disabled:bg-slate-50 disabled:text-slate-400"
              />
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {RESOURCE_TYPE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                    generationForm.resource_types.includes(option.value)
                      ? 'border-cyan-300 bg-cyan-50 text-cyan-700'
                      : 'border-slate-200 bg-white text-slate-600'
                  } ${generationProcessing || generating ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:border-cyan-200'}`}
                >
                  <input
                    type="checkbox"
                    checked={generationForm.resource_types.includes(option.value)}
                    disabled={generationProcessing || generating}
                    onChange={() => handleGenerationTypeToggle(option.value)}
                    className="h-4 w-4 accent-cyan-600"
                  />
                  {option.label}
                </label>
              ))}
            </div>

            {!hasReadyKnowledge && (
              <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                知识库就绪且存在知识切片后才能生成学习资源。
              </div>
            )}
            {hasReadyKnowledge && hasActiveKnowledgeGraph && !hasExplicitResourceTarget && (
              <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                将按 KG 节点自动生成并挂载资源。
              </div>
            )}
            {hasReadyKnowledge && !hasActiveKnowledgeGraph && !hasExplicitResourceTarget && (
              <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
                先刷新 active 知识图谱后，才能按 KG 节点自动生成资源。
              </div>
            )}

            <div data-testid="catalog-generation-task-status" className="mt-4">
              {generationTask ? (
                <div className="space-y-2 rounded-lg bg-slate-50 p-3 text-sm">
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-500">task_id</span>
                    <span className="break-all font-mono text-xs text-slate-800">{generationTask.task_id || '—'}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="text-slate-500">status</span>
                    <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(generationTask.status)}`}>
                      {formatTaskStatus(generationTask.status)}
                    </span>
                  </div>
                  <div>
                    <div className="mb-1 flex justify-between text-xs text-slate-500">
                      <span>progress</span>
                      <span>{generationTask.progress ?? 0}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-cyan-500 transition-all"
                        style={{ width: `${Math.max(0, Math.min(100, generationTask.progress ?? 0))}%` }}
                      />
                    </div>
                  </div>
                  {(generationTask.error_message || generationTaskError) && (
                    <div className="break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                      {generationTask.error_message || generationTaskError}
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-500">
                  {generationTaskError || '选择资源类型后可触发生成任务。'}
                </div>
              )}
            </div>
          </section>

          <section className="mb-5 rounded-lg border border-slate-200 bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <h3 className="text-sm font-bold text-slate-900">生成资源列表</h3>
              {loading && <span className="text-xs text-slate-400">加载中...</span>}
            </div>
            <div className="max-h-80 overflow-y-auto">
              {resources.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-400">暂无生成资源</div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {resources.map((resource) => (
                    <div key={resource.id || resource.title} data-testid="catalog-resource-row" className="px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="break-words text-sm font-semibold text-slate-900">{resource.title || '未命名资源'}</div>
                          <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                            <span>{formatResourceType(resource.type)}</span>
                            {resource.chapter && <span>章节 {resource.chapter}</span>}
                            {resource.knowledge_point && <span>知识点 {resource.knowledge_point}</span>}
                            <span>浏览 {resource.view_count ?? 0}</span>
                            <span>创建 {formatDateTime(resource.created_at)}</span>
                          </div>
                          {resource.description && (
                            <div className="mt-2 break-words text-xs text-slate-500">
                              {resource.description}
                            </div>
                          )}
                        </div>
                        <button
                          type="button"
                          aria-label="删除资源"
                          title="删除资源"
                          disabled={resourceDeleteDisabled || deletingResourceIds.has(resource.id) || !resource.id}
                          onClick={() => handleDeleteResource(resource)}
                          className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg transition-colors ${
                            resourceDeleteDisabled || deletingResourceIds.has(resource.id) || !resource.id
                              ? 'cursor-not-allowed text-slate-300'
                              : 'text-red-500 hover:bg-red-50 hover:text-red-700'
                          }`}
                        >
                          <span className="material-symbols-outlined text-[18px]">
                            {deletingResourceIds.has(resource.id) ? 'progress_activity' : 'delete'}
                          </span>
                        </button>
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
                  <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(activeTask.status)}`}>{formatTaskStatus(activeTask.status)}</span>
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
