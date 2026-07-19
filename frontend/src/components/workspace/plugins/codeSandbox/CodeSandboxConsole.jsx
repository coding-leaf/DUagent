import { getResultBadge, isCompilationFailure } from './codeSandboxViewModel';

export default function CodeSandboxConsole({ result, isRunning }) {
  const badge = result ? getResultBadge(result) : null;

  return (
    <div className="flex flex-col space-y-1.5">
      <div className="text-slate-700 text-xs font-semibold flex items-center justify-between">
        <span>🖥️ 控制台终端输出</span>
        {badge && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${badge.className}`}>
            {badge.label}
          </span>
        )}
      </div>

      <div className="bg-slate-950 border border-slate-900 rounded-xl p-4 font-mono text-xs overflow-y-auto max-h-[140px] min-h-[90px] text-slate-300 space-y-1 select-text">
        {!result && !isRunning && (
          <span className="text-slate-500 italic">点击下方「运行代码」按钮执行程序查看输出...</span>
        )}
        {isRunning && (
          <span className="text-cyan-400 animate-pulse">⚙️ 正在向隔离沙箱投递评测任务，编译并执行中...</span>
        )}
        {result && (
          <>
            {['accepted', 'wrong_answer'].includes(result.status) && (
              <div className={result.status === 'accepted' ? 'text-emerald-400' : 'text-rose-400'}>
                {result.status === 'accepted' ? '✅ 全部固定用例通过' : '❌ 固定用例未通过'}
                <span className="ml-2">{result.passed_cases}/{result.total_cases}</span>
                {result.failed_case?.visibility === 'hidden' && <p className="mt-1">隐藏用例未通过</p>}
              </div>
            )}

            {result.status === 'degraded' && (
              <div className="text-amber-400 font-semibold mb-1">
                ⚠️ 评测机提示: {result.message || '外部评测环境网络超时'}
              </div>
            )}

            {isCompilationFailure(result) && (
              <div className="text-rose-400 whitespace-pre-wrap font-mono">
                {result.compile_output || '编译失败，但评测机未返回具体错误信息。'}
              </div>
            )}

            {!isCompilationFailure(result) && result.compile_status === 'OK' && result.execution && (
              <div className="space-y-1">
                {result.execution.stdout ? (
                  <div className="text-slate-100 whitespace-pre-wrap">{result.execution.stdout}</div>
                ) : (
                  <div className="text-slate-500 italic">(程序运行无标准输出)</div>
                )}

                {result.execution.stderr && (
                  <div className="text-rose-400 whitespace-pre-wrap mt-1">
                    {result.execution.stderr}
                  </div>
                )}

                <div className="text-[10px] text-slate-500 border-t border-slate-900/60 pt-1.5 mt-2 flex justify-between">
                  <span>状态: {result.execution.status_description}</span>
                  <span>耗时: {result.execution.run_time_ms} ms</span>
                  <span>内存: {result.execution.memory_kb} KB</span>
                  <span>退出码: {result.execution.exit_code}</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
