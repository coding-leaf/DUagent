import { useCallback, useEffect, useMemo, useState } from 'react';
import useSWR from 'swr';
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
  const catalogId = catalog?.id;

  // SWR hooks for fetching course catalog details
  const {
    data: materialsData,
    error: materialsError,
    mutate: mutateMaterials,
  } = useSWR(
    catalogId && open ? ['catalog/materials', catalogId] : null,
    () => catalogService.getCourseCatalogMaterials(catalogId).then(res => res.data?.materials || []),
    { revalidateOnFocus: false }
  );

  const {
    data: statusData,
    error: statusError,
    mutate: mutateStatus,
  } = useSWR(
    catalogId && open ? ['catalog/status', catalogId] : null,
    () => catalogService.getCourseCatalogStatus(catalogId).then(res => res.data || null),
    { revalidateOnFocus: false }
  );

  const {
    data: resourcesData,
    error: resourcesError,
    mutate: mutateResources,
  } = useSWR(
    catalogId && open ? ['catalog/resources', catalogId] : null,
    () => catalogService.getCourseCatalogResources(catalogId, { page: 1, page_size: 50 }).then(res => res.data?.resources || []),
    { revalidateOnFocus: false }
  );

  const {
    data: kgStatusData,
    error: kgStatusError,
    mutate: mutateKgStatus,
  } = useSWR(
    catalogId && open ? ['catalog/kg-status', catalogId] : null,
    () => catalogService.getCourseCatalogKnowledgeGraphStatus(catalogId).then(res => res.data || null),
    { revalidateOnFocus: false }
  );

  // States for active tasks (task_id)
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [generationTaskId, setGenerationTaskId] = useState(null);
  const [kgTaskId, setKgTaskId] = useState(null);
  const [quizGenTaskId, setQuizGenTaskId] = useState(null);

  // States for operation status
  const [uploadQueue, setUploadQueue] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [knowledgeGraphGenerating, setKnowledgeGraphGenerating] = useState(false);
  const [quizGenerating, setQuizGenerating] = useState(false);

  // Task errors
  const [taskError, setTaskError] = useState('');
  const [generationTaskError, setGenerationTaskError] = useState('');
  const [knowledgeGraphTaskError, setKnowledgeGraphTaskError] = useState('');
  const [quizGenTaskError, setQuizGenTaskError] = useState('');
  const [error, setError] = useState('');

  // Delete queues/states
  const [deletingMaterialIds, setDeletingMaterialIds] = useState(() => new Set());
  const [deletingResourceIds, setDeletingResourceIds] = useState(() => new Set());

  // Generation form
  const [generationForm, setGenerationForm] = useState(createGenerationForm);

  // SWR conditional polling for tasks
  const { data: activeTaskSWR } = useSWR(
    activeTaskId && open ? ['taskStatus/ingestion', activeTaskId] : null,
    () => taskService.getTaskStatus(activeTaskId).then(res => normalizeTask(res.data, activeTaskId)),
    {
      refreshInterval: (data) => {
        if (data && (data.status === 'completed' || data.status === 'failed')) {
          return 0;
        }
        return 2000;
      },
      revalidateOnFocus: false
    }
  );

  const { data: generationTaskSWR } = useSWR(
    generationTaskId && open ? ['taskStatus/generation', generationTaskId] : null,
    () => taskService.getTaskStatus(generationTaskId).then(res => normalizeTask(res.data, generationTaskId, 'resource_generation')),
    {
      refreshInterval: (data) => {
        if (data && (data.status === 'completed' || data.status === 'failed')) {
          return 0;
        }
        return 2000;
      },
      revalidateOnFocus: false
    }
  );

  const { data: kgTaskSWR } = useSWR(
    kgTaskId && open ? ['taskStatus/kg', kgTaskId] : null,
    () => taskService.getTaskStatus(kgTaskId).then(res => normalizeTask(res.data, kgTaskId, 'kg_generation')),
    {
      refreshInterval: (data) => {
        if (data && (data.status === 'completed' || data.status === 'failed')) {
          return 0;
        }
        return 2000;
      },
      revalidateOnFocus: false
    }
  );

  const { data: quizGenTaskSWR } = useSWR(
    quizGenTaskId && open ? ['taskStatus/quiz', quizGenTaskId] : null,
    () => taskService.getTaskStatus(quizGenTaskId).then(res => normalizeTask(res.data, quizGenTaskId, 'quiz_generation')),
    {
      refreshInterval: (data) => {
        if (data && (data.status === 'completed' || data.status === 'partial' || data.status === 'failed')) {
          return 0;
        }
        return 2000;
      },
      revalidateOnFocus: false
    }
  );

  // Derived tasks
  const activeTask = useMemo(
    () => activeTaskSWR || (activeTaskId ? { task_id: activeTaskId, status: 'processing', progress: 0 } : null),
    [activeTaskSWR, activeTaskId]
  );
  const generationTask = useMemo(
    () => generationTaskSWR || (generationTaskId ? { task_id: generationTaskId, status: 'processing', progress: 0 } : null),
    [generationTaskSWR, generationTaskId]
  );
  const knowledgeGraphTask = useMemo(
    () => kgTaskSWR || (kgTaskId ? { task_id: kgTaskId, status: 'processing', progress: 0 } : null),
    [kgTaskSWR, kgTaskId]
  );
  const quizGenTask = useMemo(
    () => quizGenTaskSWR || (quizGenTaskId ? { task_id: quizGenTaskId, status: 'processing', progress: 0 } : null),
    [quizGenTaskSWR, quizGenTaskId]
  );

  // Mutation helper for refreshing all SWR queries
  const mutateAll = useCallback(async () => {
    await Promise.all([
      mutateMaterials(),
      mutateStatus(),
      mutateResources(),
      mutateKgStatus(),
    ]);
  }, [mutateMaterials, mutateStatus, mutateResources, mutateKgStatus]);

  // Synchronize loading error details
  useEffect(() => {
    if (materialsError) setError(getErrorMessage(materialsError, '课程资源库详情加载失败'));
    else if (statusError) setError(getErrorMessage(statusError, '课程资源库详情加载失败'));
    else if (resourcesError) setError(getErrorMessage(resourcesError, '课程资源库详情加载失败'));
    else if (kgStatusError) setError(getErrorMessage(kgStatusError, '课程资源库详情加载失败'));
  }, [materialsError, statusError, resourcesError, kgStatusError]);

  // Reset task/state on catalogId or open state change
  useEffect(() => {
    setActiveTaskId(null);
    setGenerationTaskId(null);
    setKgTaskId(null);
    setQuizGenTaskId(null);
    setUploadQueue([]);
    setUploading(false);
    setIngesting(false);
    setGenerating(false);
    setKnowledgeGraphGenerating(false);
    setQuizGenerating(false);
    setTaskError('');
    setGenerationTaskError('');
    setKnowledgeGraphTaskError('');
    setQuizGenTaskError('');
    setError('');
    setDeletingMaterialIds(new Set());
    setDeletingResourceIds(new Set());
    setGenerationForm(createGenerationForm());
  }, [catalogId, open]);

  // Detect and set ongoing tasks from fetched statuses
  const incomingTaskId = statusData?.last_ingestion_task_id;
  const isIncomingIngesting = statusData?.status === 'ingesting' || statusData?.knowledge_status === 'ingesting';
  const incomingTaskStatus = statusData?.last_ingestion_status || 'processing';
  const isTerminalTask = incomingTaskStatus === 'completed' || incomingTaskStatus === 'failed';

  useEffect(() => {
    if (isIncomingIngesting && incomingTaskId && !isTerminalTask) {
      setActiveTaskId(incomingTaskId);
    }
  }, [isIncomingIngesting, incomingTaskId, isTerminalTask]);

  const incomingKgTask = kgStatusData?.last_generation_task;
  useEffect(() => {
    if (incomingKgTask?.task_id && incomingKgTask.status === 'processing') {
      setKgTaskId(incomingKgTask.task_id);
    }
  }, [incomingKgTask?.task_id, incomingKgTask?.status]);

  // Handle active task status transitions
  useEffect(() => {
    if (!activeTask) return;
    if (activeTask.status === 'completed' || activeTask.status === 'failed') {
      setIngesting(false);
      if (activeTask.status === 'failed') {
        setTaskError(activeTask.error_message || '课程资源库入库失败');
      }
      mutateAll();
      if (onChanged) onChanged();
    } else {
      setIngesting(true);
      setTaskError('');
    }
  }, [activeTask, mutateAll, onChanged]);

  // Handle resource generation task transitions
  useEffect(() => {
    if (!generationTask) return;
    if (generationTask.status === 'completed' || generationTask.status === 'failed') {
      setGenerating(false);
      if (generationTask.status === 'failed') {
        setGenerationTaskError(generationTask.error_message || '学习资源生成失败');
      }
      mutateAll();
      if (onChanged) onChanged();
    } else {
      setGenerating(true);
      setGenerationTaskError('');
    }
  }, [generationTask, mutateAll, onChanged]);

  // Handle knowledge graph generation task transitions
  useEffect(() => {
    if (!knowledgeGraphTask) return;
    if (knowledgeGraphTask.status === 'completed' || knowledgeGraphTask.status === 'failed') {
      setKnowledgeGraphGenerating(false);
      if (knowledgeGraphTask.status === 'failed') {
        setKnowledgeGraphTaskError(knowledgeGraphTask.error_message || '知识图谱生成失败');
      }
      mutateAll();
      if (onChanged) onChanged();
    } else {
      setKnowledgeGraphGenerating(true);
      setKnowledgeGraphTaskError('');
    }
  }, [knowledgeGraphTask, mutateAll, onChanged]);

  // Handle quiz generation task transitions
  useEffect(() => {
    if (!quizGenTask) return;
    if (quizGenTask.status === 'completed' || quizGenTask.status === 'partial' || quizGenTask.status === 'failed') {
      setQuizGenerating(false);
      if (quizGenTask.status === 'failed') {
        setQuizGenTaskError(quizGenTask.error_message || '题库生成失败');
      }
      mutateAll();
      if (onChanged) onChanged();
    } else {
      setQuizGenerating(true);
      setQuizGenTaskError('');
    }
  }, [quizGenTask, mutateAll, onChanged]);

  // Derived layout-specific properties
  const materials = useMemo(() => materialsData || [], [materialsData]);
  const resources = useMemo(() => resourcesData || [], [resourcesData]);
  const knowledgeStatus = statusData || null;
  const knowledgeGraphStatus = kgStatusData || null;

  const loading = open && ((!materialsData && !materialsError) || (!resourcesData && !resourcesError));

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
    && activeTask.task_id === knowledgeStatus?.last_ingestion_task_id;
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

  // Handlers
  const handleUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!catalogId || files.length === 0 || uploadDisabled) return;

    const queuedFiles = files.map((file, index) => ({
      id: `${Date.now()}-${index}-${file.name}`,
      name: file.name,
      status: 'queued',
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
        const res = await catalogService.uploadCourseCatalogMaterial(catalogId, files[index]);
        setUploadQueue((prev) => prev.map((queueItem) => (
          queueItem.id === item.id
            ? { ...queueItem, status: 'uploaded', message: res.message || '上传完成' }
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
    await mutateAll();
    if (onChanged) onChanged();
  };

  const handleStartIngestion = async () => {
    if (!catalogId || startDisabled) return;
    setIngesting(true);
    setTaskError('');
    setError('');
    try {
      const res = await catalogService.startCourseCatalogIngestion(catalogId);
      const task = normalizeTask(res.data);
      setActiveTaskId(task.task_id);
    } catch (err) {
      console.error('course catalog ingestion start error', err);
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
    setKnowledgeGraphGenerating(true);
    setKnowledgeGraphTaskError('');
    setError('');
    try {
      const res = await catalogService.startCourseCatalogKnowledgeGraphGeneration(catalogId);
      const task = normalizeTask(res.data, res.data?.task_id, 'kg_generation');
      setKgTaskId(task.task_id);
    } catch (err) {
      console.error('course catalog knowledge graph generation start error', err);
      setKnowledgeGraphTaskError(getErrorMessage(err, '知识图谱生成启动失败'));
      setKnowledgeGraphGenerating(false);
    }
  };

  const handleStartGeneration = async () => {
    if (!catalogId || generationDisabled) return;
    setGenerating(true);
    setGenerationTaskError('');
    setError('');
    try {
      const payload = {
        chapter: generationForm.chapter.trim(),
        knowledge_point: generationForm.knowledge_point.trim(),
        resource_types: generationForm.resource_types
      };
      const res = await catalogService.startCourseCatalogResourceGeneration(catalogId, payload);
      const task = normalizeTask(res.data, res.data?.task_id, 'resource_generation');
      setGenerationTaskId(task.task_id);
    } catch (err) {
      console.error('course catalog resource generation start error', err);
      setGenerationTaskError(getErrorMessage(err, '学习资源生成启动失败'));
      setGenerating(false);
    }
  };

  const handleStartQuizGeneration = useCallback(async () => {
    if (!catalog || quizGenerating) return;
    setQuizGenerating(true);
    setQuizGenTaskError('');
    setQuizGenTaskId(null);
    try {
      const res = await catalogService.startQuizGeneration(catalog.id);
      if (res.code === 202) {
        setQuizGenTaskId(res.data.task_id);
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
      mutateMaterials(materials.filter((item) => item.id !== material.id), false);
      if (res.data?.knowledge_status) {
        mutateStatus({
          ...(statusData || {}),
          catalog_id: catalogId,
          knowledge_status: res.data.knowledge_status,
          material_count: Math.max(0, (statusData?.material_count ?? materials.length) - 1)
        }, false);
      }
      await mutateAll();
      if (onChanged) onChanged();
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
      mutateResources(resources.filter((item) => item.id !== resource.id), false);
      await mutateAll();
      if (onChanged) onChanged();
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
    generationProcessing,
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
