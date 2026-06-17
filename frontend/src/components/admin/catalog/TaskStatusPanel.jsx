import { getBadgeClass, formatTaskStatus } from './formatters';

export default function TaskStatusPanel({ task, taskError, fallbackText, 'data-testid': testId }) {
  return (
    <div data-testid={testId} className="mt-4">
      {task ? (
        <div className="space-y-2 rounded-lg bg-slate-50 p-3 text-sm">
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">task_id</span>
            <span className="break-all font-mono text-xs text-slate-800">{task.task_id || '—'}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-slate-500">status</span>
            <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(task.status)}`}>
              {formatTaskStatus(task.status)}
            </span>
          </div>
          <div>
            <div className="mb-1 flex justify-between text-xs text-slate-500">
              <span>progress</span>
              <span>{task.progress ?? 0}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-cyan-500 transition-all"
                style={{ width: `${Math.max(0, Math.min(100, task.progress ?? 0))}%` }}
              />
            </div>
          </div>
          {(task.error_message || taskError) && (
            <div className="break-words rounded bg-red-50 px-2 py-1 text-xs text-red-700">
              {task.error_message || taskError}
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-500">
          {taskError || fallbackText}
        </div>
      )}
    </div>
  );
}
