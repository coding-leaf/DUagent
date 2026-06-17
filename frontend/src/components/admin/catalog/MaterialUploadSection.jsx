import Icon from '../../Icon';
import { getBadgeClass, formatUploadQueueStatus } from './formatters';

export default function MaterialUploadSection({ uploadQueue, uploading, uploadDisabled, onUpload }) {
  return (
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
          <Icon name="upload_file" className="material-symbols-outlined text-[18px]"/>
          {uploading ? '上传中' : '选择文件'}
          <input
            data-testid="catalog-upload-input"
            type="file"
            accept=".txt,.md,.pdf"
            multiple
            disabled={uploadDisabled}
            onChange={onUpload}
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
  );
}
