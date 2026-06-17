import { useState, useEffect, useCallback } from 'react';
import { adminService } from '../../api/services/admin';
import Icon from '../Icon';

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const getLogRows = (data) => data?.logs || data || [];

export default function SystemLogsPanel() {
  const [agentLogs, setAgentLogs] = useState([]);
  const [operationLogs, setOperationLogs] = useState([]);
  const [activeLogType, setActiveLogType] = useState('agent');
  const [loadingLogs, setLoadingLogs] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const [agentRes, systemRes] = await Promise.all([
        adminService.getAgentLogs(),
        adminService.getSystemLogs()
      ]);
      if (agentRes.code === 200) {
        setAgentLogs(getLogRows(agentRes.data));
      }
      if (systemRes.code === 200) {
        setOperationLogs(getLogRows(systemRes.data));
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingLogs(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchLogs();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchLogs]);

  const visibleLogs = activeLogType === 'agent' ? agentLogs : operationLogs;

  return (
    <div className="animate-in fade-in duration-500 h-full flex flex-col">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">系统日志</h1>
          <p className="text-sm text-slate-500">查看 Agent 运行记录与系统操作事件。</p>
        </div>
        <button onClick={fetchLogs} className="flex items-center gap-1 text-cyan-600 hover:underline text-sm font-medium cursor-pointer">
          <Icon name="refresh" className="material-symbols-outlined text-[18px]"/> 刷新日志
        </button>
      </div>

      <div className="mb-4 inline-flex rounded-lg border border-slate-200 bg-white p-1">
        <button
          type="button"
          onClick={() => setActiveLogType('agent')}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            activeLogType === 'agent' ? 'bg-cyan-600 text-white' : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          Agent 日志
        </button>
        <button
          type="button"
          onClick={() => setActiveLogType('system')}
          className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
            activeLogType === 'system' ? 'bg-cyan-600 text-white' : 'text-slate-600 hover:bg-slate-50'
          }`}
        >
          系统日志
        </button>
      </div>

      <div className="flex-1 bg-[#0f172a] rounded-xl border border-slate-800 shadow-xl overflow-hidden flex flex-col font-mono text-sm">
        <div className="flex items-center gap-2 px-4 py-3 bg-[#1e293b] border-b border-slate-800">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <div className="w-3 h-3 rounded-full bg-amber-500"></div>
          <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
          <span className="ml-4 text-xs text-slate-400 font-sans tracking-wider uppercase">Orchestrator Terminal</span>
        </div>
        <div className="p-4 overflow-y-auto flex-1 space-y-2 text-slate-300">
          {loadingLogs ? (
            <div className="text-cyan-500 animate-pulse">Connecting to Agent Mesh...</div>
          ) : visibleLogs.length === 0 ? (
            <div className="text-slate-500">
              {activeLogType === 'agent' ? '暂无 Agent 日志' : '暂无系统日志'}
            </div>
          ) : activeLogType === 'agent' ? (
            agentLogs.map((log) => (
              <div key={`${log.timestamp}-${log.endpoint}-${log.agent_type}`} className="flex gap-4 hover:bg-white/5 p-1 rounded transition-colors group">
                <span className="text-slate-500 flex-shrink-0 w-52">[{formatDateTime(log.timestamp)}]</span>
                <span className={`font-bold flex-shrink-0 w-28 ${
                  log.status === 'error' ? 'text-red-400' : 'text-cyan-400'
                }`}>
                  {log.status?.toUpperCase() || 'INFO'}
                </span>
                <span className="text-emerald-400 flex-shrink-0 w-36">[{log.agent_type || '—'}]</span>
                <span className="flex-1 break-all text-slate-200">
                  {log.endpoint}{log.error_message ? ` — ${log.error_message}` : ''}
                  <span className="ml-2 text-xs text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">
                    (Lat: {log.latency_ms}ms, Tokens: {log.tokens_used})
                  </span>
                </span>
              </div>
            ))
          ) : (
            operationLogs.map((log) => (
              <div key={`${log.timestamp}-${log.event_type}-${log.user_id || 'system'}`} className="flex gap-4 hover:bg-white/5 p-1 rounded transition-colors group">
                <span className="text-slate-500 flex-shrink-0 w-52">[{formatDateTime(log.timestamp)}]</span>
                <span className={`font-bold flex-shrink-0 w-32 ${
                  log.event_type === 'system_error' || log.event_type === 'security' ? 'text-red-400' : 'text-cyan-400'
                }`}>
                  {log.event_type?.toUpperCase() || 'OPERATION'}
                </span>
                <span className="text-emerald-400 flex-shrink-0 w-40">[{log.user_id || 'system'}]</span>
                <span className="flex-1 break-all text-slate-200">
                  {log.description || '—'}
                  <span className="ml-2 text-xs text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">
                    (IP: {log.ip_address || '—'}, Detail: {log.detail ? JSON.stringify(log.detail) : '{}'})
                  </span>
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
