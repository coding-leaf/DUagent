export const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

export const formatFileSize = (value) => {
  if (value === undefined || value === null) return '—';
  const size = Number(value);
  if (Number.isNaN(size)) return String(value);
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
};

export const getBadgeClass = (status) => {
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

export const formatCatalogStatus = createStatusLabelFormatter({
  draft: '未入库',
  ingesting: '入库中',
  ready: '可绑定',
  failed: '入库失败'
}, 'UNKNOWN');

export const formatKnowledgeStatus = createStatusLabelFormatter({
  draft: '未入库',
  ingesting: '入库中',
  ready: '已同步',
  dirty: '待更新',
  partial: '部分失败',
  failed: '入库失败'
}, 'UNKNOWN');

export const formatMaterialStatus = createStatusLabelFormatter({
  uploaded: '已上传',
  ingesting: '入库中',
  ingested: '已入库',
  failed: '入库失败'
}, 'UNKNOWN');

export const formatUploadQueueStatus = createStatusLabelFormatter({
  queued: '等待上传',
  uploading: '上传中',
  uploaded: '已上传',
  failed: '上传失败'
}, 'UNKNOWN');

export const formatTaskStatus = createStatusLabelFormatter({
  processing: '处理中',
  completed: '已完成',
  partial: '部分失败',
  failed: '失败'
}, '—');

export const formatResourceType = createStatusLabelFormatter({
  lesson: '标准讲义',
  diagram: '知识图解',
  example: '代码示例',
  document: '旧版文档',
  mindmap: '旧版思维导图',
  reading: '旧版阅读材料',
  code: '旧版代码示例'
}, 'UNKNOWN');

export const RESOURCE_TYPE_OPTIONS = [
  { value: 'lesson', label: '标准讲义' },
  { value: 'diagram', label: '知识图解' },
  { value: 'example', label: '代码示例' }
];
