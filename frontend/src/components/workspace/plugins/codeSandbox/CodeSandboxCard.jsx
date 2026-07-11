import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChat } from '../../../../context/ChatContext';
import Icon from '../../../Icon';
import CodeSandboxConsole from './CodeSandboxConsole';
import { buildAskAIPrompt, getSourceFilename } from './codeSandboxViewModel';
import { useCodeSandboxExecution } from './useCodeSandboxExecution';
import { useCodeProblem } from './useCodeProblem';

const markdownComponents = {
  h1: ({ children, ...props }) => (
    <h1 className="text-base font-bold text-slate-900 mt-4 mb-2 pb-1 border-b border-slate-200" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="text-sm font-semibold text-slate-800 mt-3 mb-1.5" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="text-xs font-semibold text-slate-700 mt-2 mb-1" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }) => (
    <p className="text-slate-600 leading-relaxed mb-2 text-xs" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="list-disc pl-4 mb-2 space-y-0.5 text-xs text-slate-600" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="list-decimal pl-4 mb-2 space-y-0.5 text-xs text-slate-600" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-slate-600 text-xs" {...props}>
      {children}
    </li>
  ),
  code: ({ node, inline, className, children, ...props }) => {
    return inline ? (
      <code className="bg-slate-100 text-slate-800 px-1 py-0.5 rounded font-mono text-[10px]" {...props}>
        {children}
      </code>
    ) : (
      <pre className="bg-slate-100 text-slate-800 p-2 rounded-lg font-mono text-[10px] overflow-x-auto my-1.5 border border-slate-200 whitespace-pre-wrap max-w-full">
        <code {...props}>{children}</code>
      </pre>
    );
  }
};

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

      <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 text-slate-700 text-sm leading-relaxed shadow-sm">
        <div className="flex items-center gap-1.5 border-b border-slate-250 pb-2 mb-3">
          <Icon name="assignment" className="text-slate-600 text-sm shrink-0" />
          <span className="font-semibold text-slate-800 text-xs uppercase tracking-wider">题目描述 & 要求</span>
        </div>
        <div className="prose prose-sm max-w-none text-slate-750">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {questionText}
          </ReactMarkdown>
        </div>
        {problem?.public_cases?.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-200/80">
            <div className="flex items-center gap-1.5 mb-2">
              <Icon name="analytics" className="text-slate-500 text-xs shrink-0" />
              <span className="font-semibold text-slate-600 text-xs uppercase tracking-wider">公开测试用例：</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {problem.public_cases.map((testCase, index) => (
                <div key={index} className="bg-white border border-slate-200/80 rounded-lg p-2.5 font-mono text-[11px] text-slate-600 shadow-sm flex flex-col gap-1.5">
                  <div className="flex items-center gap-2 border-b border-slate-100 pb-1 mb-0.5">
                    <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-semibold">示例 {index + 1}</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400 font-semibold w-10 shrink-0">输入:</span>
                      <code className="bg-slate-50 text-slate-700 px-1.5 py-0.5 rounded font-mono text-[10px] max-w-full overflow-x-auto truncate">{testCase.stdin || '(空)'}</code>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-slate-400 font-semibold w-10 shrink-0">输出:</span>
                      <code className="bg-slate-50 text-slate-700 px-1.5 py-0.5 rounded font-mono text-[10px] max-w-full overflow-x-auto truncate">{testCase.expected_output}</code>
                    </div>
                  </div>
                </div>
              ))}
            </div>
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
