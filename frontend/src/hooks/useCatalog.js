import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { catalogService } from '../api/services/catalog';
import { taskService } from '../api/services/task';
import { getErrorMessage } from '../utils/apiError';

const normalizeTask = (task, fallbackId, fallbackType = 'course_catalog_ingestion') => ({
  id: task?.id || task?.task_id || fallbackId || '',
  task_id: task?.task_id || fallbackId || '',
  task_type: task?.task_type || fallbackType,
  status: task?.status || 'processing',
  progress: task?.progress ?? 0,
  error_message: task?.error_message || '',
  result: task?.result || null,
  created_at: task?.created_at,
  completed_at: task?.completed_at
});

const createGenerationForm = () => ({
  chapter: '',
  knowledge_point: '',
  resource_types: []
});

export function useCatalog({ catalog, open, onChanged }) {
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
  const [quizGenerating, setQuizGenerating] = useState(false);
  const [quizGenTask, setQuizGenTask] = useState(null);
  const [quizGenTaskError, setQuizGenTaskError] = useState('');
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
    if (!catalogId || !openRef.current) return false;

    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    setLoading(true);
    setError('');
    try {
      const [materialsRes, statusRes, resourcesRes, knowledgeGraphRes] = await Promise.all([
        catalogService.getCourseCatalogMaterials(catalogId),
        catalogService.getCourseCatalogStatus(catalogId),
        catalogService.getCourseCatalogResources(catalogId, { page: 1, page_size: 50 }),
        catalogService.getCourseCatalogKnowledgeGraphStatus(catalogId)
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
  }, [canWriteRequest, catalogId]);

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

  useEffect(() => {
    if (
      !quizGenTask?.task_id
      || quizGenTask.status === 'completed'
      || quizGenTask.status === 'partial'
      || quizGenTask.status === 'failed'
    ) return;

    let cancelled = false;
    let timeoutId;

    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(quizGenTask.task_id);
        if (cancelled) return;
        const task = normalizeTask(res.data, quizGenTask.task_id, 'quiz_generation');
        setQuizGenTask(task);
        if (task.status === 'completed' || task.status === 'partial' || task.status === 'failed') {
          setQuizGenerating(false);
          if (onChanged) onChanged();
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        console.error('quiz generation task poll error', err);
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
  }, [quizGenTask?.task_id, quizGenTask?.status, onChanged]);

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
        const res = await catalogService.uploadCourseCatalogMaterial(operationCatalogId, files[index]);
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
      const res = await catalogService.startCourseCatalogIngestion(operationCatalogId);
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
      const res = await catalogService.startCourseCatalogKnowledgeGraphGeneration(operationCatalogId);
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
      const res = await catalogService.startCourseCatalogResourceGeneration(operationCatalogId, payload);
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

  const handleStartQuizGeneration = useCallback(async () => {
    if (!catalog || quizGenerating) return;
    setQuizGenerating(true);
    setQuizGenTaskError('');
    setQuizGenTask(null);
    try {
      const res = await catalogService.startQuizGeneration(catalog.id);
      if (res.code === 202) {
        setQuizGenTask({ task_id: res.data.task_id, status: 'processing', progress: 10 });
      }
    } catch (err) {
      console.error('Failed to start quiz generation:', err);
      setQuizGenerating(false);
      setQuizGenTaskError(getErrorMessage(err, '题库生成启动失败'));
    }
  }, [catalog, quizGenerating]);

  const handleDeleteMaterial = async (material) => {
    if (!catalogId || !material?.id || materialDeleteDisabled || deletingMaterialIds.has(material.id)) return;

    setDeletingMaterialIds((prev) => new Set(prev).add(material.id));
    setError('');
    try {
      const res = await catalogService.deleteCourseCatalogMaterial(catalogId, material.id);
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
      await catalogService.deleteResource(resource.id);
      setResources((prev) => prev.filter((item) => item.id !== resource.id));
      const refreshed = await refreshDetails();
      if (refreshed && onChanged) onChanged();
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

  return {
    materials,
    resources,
    knowledgeStatus,
    knowledgeGraphStatus,
    loading,
    error,
    uploadQueue,
    uploading,
    ingesting,
    activeTask,
    taskError,
    generationForm,
    generating,
    generationTask,
    generationTaskError,
    knowledgeGraphGenerating,
    knowledgeGraphTask,
    knowledgeGraphTaskError,
    quizGenerating,
    quizGenTask,
    quizGenTaskError,
    deletingMaterialIds,
    deletingResourceIds,
    uploadDisabled,
    startDisabled,
    generationDisabled,
    materialDeleteDisabled,
    resourceDeleteDisabled,
    knowledgeGraphGenerationDisabled,
    hasReadyKnowledge,
    hasActiveKnowledgeGraph,
    hasExplicitResourceTarget,
    summary,
    hasIngestibleMaterials,
    taskProcessing,
    knowledgeGraphProcessing,
    handleUpload,
    handleStartIngestion,
    handleGenerationFieldChange,
    handleGenerationTypeToggle,
    handleStartKnowledgeGraphGeneration,
    handleStartGeneration,
    handleStartQuizGeneration,
    handleDeleteMaterial,
    handleDeleteResource,
  };
}
