import { useMemo, useState } from 'react';
import { useChat } from '../../context/ChatContext';
import Icon from '../Icon';

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'error', label: '错误' },
  { key: 'tool', label: '工具' },
  { key: 'model', label: '模型' },
];

export default function DeveloperConsoleFloatingPanel() {
  const { runLogs = [], clearRunLogs } = useChat();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [expandedLogId, setExpandedLogId] = useState(null);

  const visible = import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEV_CONSOLE === 'true';
  const filteredLogs = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return runLogs.filter(log => {
      const matchesFilter =
        filter === 'all'
        || (filter === 'error' && (log.level === 'error' || log.type === 'workflow_failed'))
        || (filter === 'tool' && (log.type?.includes('tool') || log.message?.includes('tool') || log.payload?.tool_name))
        || (filter === 'model' && (log.message?.includes('model') || log.payload?.model));
      if (!matchesFilter) return false;
      if (!normalizedQuery) return true;
      return JSON.stringify(log).toLowerCase().includes(normalizedQuery);
    });
  }, [filter, query, runLogs]);

  if (!visible) return null;

  const copyLogs = async () => {
    await navigator.clipboard?.writeText(JSON.stringify(runLogs, null, 2));
  };

  return (
    <div className="fixed bottom-4 right-4 z-[90] font-['Public_Sans']">
      {open && (
        <section className="mb-3 w-[min(92vw,520px)] h-[min(70vh,560px)] bg-slate-950 text-slate-100 border border-slate-700 shadow-2xl rounded-xl overflow-hidden flex flex-col">
          <header className="h-11 px-3 border-b border-slate-800 flex items-center justify-between bg-slate-900">
            <div className="flex items-center gap-2 min-w-0">
              <Icon name="terminal" className="material-symbols-outlined text-[18px] text-cyan-300" />
              <span className="text-sm font-semibold">Dev Console</span>
              <span className="text-[11px] text-slate-400">{runLogs.length} logs</span>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={copyLogs} className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700">
                复制
              </button>
              <button onClick={clearRunLogs} className="px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700">
                清空
              </button>
              <button onClick={() => setOpen(false)} className="w-7 h-7 rounded hover:bg-slate-800 flex items-center justify-center">
                <Icon name="close" className="material-symbols-outlined text-[16px]" />
              </button>
            </div>
          </header>

          <div className="px-3 py-2 border-b border-slate-800 flex gap-1 bg-slate-950">
            {FILTERS.map(item => (
              <button
                key={item.key}
                onClick={() => setFilter(item.key)}
                className={`px-2 py-1 text-[11px] rounded ${filter === item.key ? 'bg-cyan-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="px-3 py-2 border-b border-slate-800 bg-slate-950">
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="搜索日志"
              className="w-full h-8 rounded bg-slate-900 border border-slate-800 px-2 text-xs text-slate-100 placeholder:text-slate-500 outline-none focus:border-cyan-500"
            />
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2 text-xs leading-relaxed">
            {filteredLogs.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-500">
                暂无日志
              </div>
            ) : filteredLogs.map(log => (
              <article key={log.id} className="rounded-lg border border-slate-800 bg-slate-900/70 p-2">
                <button
                  type="button"
                  onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                  className="w-full flex items-center justify-between gap-2 text-left"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`w-1.5 h-1.5 rounded-full ${log.level === 'error' ? 'bg-red-400' : 'bg-cyan-300'}`} />
                    <span className="font-mono text-slate-100 truncate">{log.message}</span>
                  </div>
                  <span className="font-mono text-[10px] text-slate-500">{log.type}</span>
                </button>
                <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] text-slate-400 font-mono">
                  <span className="truncate">run: {log.runId || '-'}</span>
                  <span className="truncate">source: {log.source || '-'}</span>
                  {log.payload?.tool_name && <span className="truncate">tool: {log.payload.tool_name}</span>}
                  {log.payload?.event && <span className="truncate">event: {log.payload.event}</span>}
                  {log.payload?.duration_ms && <span className="truncate">ms: {log.payload.duration_ms}</span>}
                  {log.payload?.state && <span className="truncate">state: {log.payload.state}</span>}
                </div>
                {expandedLogId === log.id && (
                  <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-950 border border-slate-800 p-2 text-[10px] text-slate-300 whitespace-pre-wrap break-words">
                    {JSON.stringify(log.payload, null, 2)}
                  </pre>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <button
        onClick={() => setOpen(!open)}
        className="h-10 px-3 rounded-full bg-slate-950 text-white border border-slate-700 shadow-xl flex items-center gap-2 text-xs font-semibold hover:bg-slate-900"
      >
        <Icon name="terminal" className="material-symbols-outlined text-[16px]" />
        Dev
        {runLogs.length > 0 && (
          <span className="min-w-5 h-5 px-1 rounded-full bg-cyan-500 text-[10px] flex items-center justify-center">
            {runLogs.length}
          </span>
        )}
      </button>
    </div>
  );
}
