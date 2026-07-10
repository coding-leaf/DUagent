import { useChat } from '../../../../context/ChatContext';
import CodeSandboxConsole from './CodeSandboxConsole';
import { buildAskAIPrompt, getSourceFilename } from './codeSandboxViewModel';
import { useCodeSandboxExecution } from './useCodeSandboxExecution';
import { useCodeProblem } from './useCodeProblem';

export default function CodeSandboxCard({ problem_id: problemId, question_text, code: legacyCode, language, default_stdin }) {
  const { sendMessage, isSending } = useChat();
  const { problem, error, isLoading } = useCodeProblem(problemId);
  const isFixedCaseProblem = Boolean(problemId);
  const {
    code,
    setCode,
    stdin,
    setStdin,
    isRunning,
    result,
    runCode,
  } = useCodeSandboxExecution({
    initialCode: problem?.starter_code || legacyCode,
    defaultStdin: default_stdin,
    language: problem?.language || language,
    problemId,
  });

  if (isLoading) return <div className="p-4 text-sm text-slate-500">正在加载代码题...</div>;
  if (error || (isFixedCaseProblem && !problem)) {
    return <div className="p-4 text-sm text-rose-600">代码题加载失败或已不可访问。</div>;
  }
  const displayLanguage = problem?.language || language;
  const questionText = problem?.statement || question_text;

  const handleAskAI = () => {
    if (isSending) return;
    sendMessage(buildAskAIPrompt({ code, language: displayLanguage, stdin, result }));
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col h-full space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h3 className="text-slate-800 font-bold text-base flex items-center gap-2">
          <span>💻 交互式编程沙箱</span>
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-cyan-50 text-cyan-700 uppercase border border-cyan-100">
            {displayLanguage}
          </span>
        </h3>
      </div>

      <div className="bg-slate-50 border border-slate-150 rounded-xl p-4 text-slate-700 text-sm leading-relaxed">
        <p className="font-semibold text-slate-800 mb-1">题目要求：</p>
        <p>{questionText}</p>
        {problem?.public_cases?.length > 0 && (
          <div className="mt-3 space-y-2 text-xs">
            <p className="font-semibold">公开示例：</p>
            {problem.public_cases.map((testCase, index) => (
              <pre key={index} className="whitespace-pre-wrap text-slate-600">输入：{testCase.stdin}输出：{testCase.expected_output}</pre>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col flex-1">
        <div className="bg-slate-800 text-slate-400 rounded-t-xl px-4 py-2 text-xs font-mono flex justify-between items-center border-b border-slate-700">
          <span>{getSourceFilename(displayLanguage)}</span>
          <span className="text-slate-500">Editable Editor</span>
        </div>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="flex-1 w-full min-h-[220px] font-mono text-sm p-4 bg-slate-900 text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 rounded-b-xl border border-slate-800 resize-y leading-relaxed"
          placeholder="请输入你的代码..."
          spellCheck="false"
        />
      </div>

      {!isFixedCaseProblem && <div className="flex flex-col space-y-1.5">
        <label className="text-slate-700 text-xs font-semibold flex items-center gap-1.5">
          <span>⌨️ 输入参数 (stdin)</span>
        </label>
        <input
          type="text"
          value={stdin}
          onChange={(e) => setStdin(e.target.value)}
          placeholder="给程序运行提供可选标准输入..."
          className="w-full text-slate-800 text-sm px-3.5 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white"
        />
      </div>}

      <CodeSandboxConsole result={result} isRunning={isRunning} />

      <div className="flex gap-3 justify-end pt-1">
        <button
          onClick={handleAskAI}
          disabled={isSending}
          className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 text-sm font-semibold rounded-xl transition-colors cursor-pointer flex items-center gap-1.5 border border-slate-200"
        >
          🙋 请求 AI 答疑
        </button>

        <button
          onClick={runCode}
          disabled={isRunning}
          className="px-4 py-2.5 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
        >
          {isFixedCaseProblem ? '🚀 提交评测' : '🚀 运行代码'}
        </button>
      </div>
    </div>
  );
}
