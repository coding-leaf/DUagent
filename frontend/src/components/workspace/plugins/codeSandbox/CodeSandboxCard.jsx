import { useState, useEffect } from 'react';
import { useChat } from '../../../../context/ChatContext';
import CodeSandboxConsole from './CodeSandboxConsole';
import { buildAskAIPrompt, getSourceFilename } from './codeSandboxViewModel';
import { useCodeSandboxExecution } from './useCodeSandboxExecution';
import { useCodeProblem } from './useCodeProblem';
import MarkdownViewer from '../../../common/MarkdownViewer';

const defaultTemplates = {
  c: '#include <stdio.h>\n\nint main() {\n    printf("Hello World\\n");\n    return 0;\n}',
  cpp: '#include <iostream>\n\nint main() {\n    std::cout << "Hello World" << std::endl;\n    return 0;\n}',
  python: 'print("Hello World")',
  java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello World");\n    }\n}',
  go: 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Hello World")\n}',
  javascript: 'console.log("Hello World");'
};

function LanguageSelector({ isFixedCase, currentLanguage, onLanguageChange }) {
  if (isFixedCase) {
    return (
      <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-cyan-50 text-cyan-700 uppercase border border-cyan-100 shrink-0">
        {currentLanguage}
      </span>
    );
  }

  return (
    <select
      value={currentLanguage}
      onChange={(e) => onLanguageChange(e.target.value)}
      className="text-xs font-semibold bg-white border border-slate-200 rounded-md px-2 py-1 text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-1 focus:ring-cyan-500 cursor-pointer shrink-0"
    >
      <option value="c">C</option>
      <option value="cpp">C++</option>
      <option value="python">Python</option>
      <option value="java">Java</option>
      <option value="go">Go</option>
      <option value="javascript">JavaScript</option>
    </select>
  );
}

function PublicTestCases({ cases }) {
  if (!cases || cases.length === 0) return null;
  return (
    <div className="mt-4 pt-4 border-t border-slate-200/60">
      <p className="font-semibold text-slate-800 text-xs mb-2">💡 公开示例（Public Test Cases）：</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {cases.map((testCase, index) => (
          <div
            key={index}
            className="bg-white/80 border border-slate-200/60 rounded-lg p-3 font-mono text-xs shadow-sm flex flex-col gap-1.5"
          >
            <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              示例 #{index + 1}
            </div>
            <div className="flex items-start gap-1">
              <span className="text-slate-400 font-bold shrink-0">输入:</span>
              <span className="text-slate-700 bg-slate-50 px-1 py-0.5 rounded border border-slate-100 min-w-[30px] inline-block">
                {testCase.stdin?.trim() || '(无输入)'}
              </span>
            </div>
            <div className="flex items-start gap-1">
              <span className="text-emerald-500 font-bold shrink-0">输出:</span>
              <span className="text-slate-700 bg-slate-50 px-1 py-0.5 rounded border border-slate-100 min-w-[30px] inline-block">
                {testCase.expected_output?.trim()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CodeEditor({ displayLanguage, code, onCodeChange }) {
  return (
    <div className="flex flex-col flex-1">
      <div className="bg-slate-800 text-slate-400 rounded-t-xl px-4 py-2 text-xs font-mono flex justify-between items-center border-b border-slate-700">
        <span>{getSourceFilename(displayLanguage)}</span>
        <span className="text-slate-500">Editable Editor</span>
      </div>
      <textarea
        value={code}
        onChange={(e) => onCodeChange(e.target.value)}
        className="flex-1 w-full min-h-[220px] font-mono text-sm p-4 bg-slate-900 text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 rounded-b-xl border border-slate-800 resize-y leading-relaxed"
        placeholder="请输入你的代码..."
        spellCheck="false"
      />
    </div>
  );
}

function StdinInput({ isFixedCase, stdin, onStdinChange }) {
  if (isFixedCase) return null;
  return (
    <div className="flex flex-col space-y-1.5">
      <label className="text-slate-700 text-xs font-semibold flex items-center gap-1.5">
        <span>⌨️ 输入参数 (stdin)</span>
      </label>
      <input
        type="text"
        value={stdin}
        onChange={(e) => onStdinChange(e.target.value)}
        placeholder="给程序运行提供可选标准输入..."
        className="w-full text-slate-800 text-sm px-3.5 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-white"
      />
    </div>
  );
}

function ActionButtons({ isSending, isRunning, isFixedCase, onAskAI, onRun }) {
  return (
    <div className="flex gap-3 justify-end pt-1">
      <button
        onClick={onAskAI}
        disabled={isSending}
        className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 text-sm font-semibold rounded-xl transition-colors cursor-pointer flex items-center gap-1.5 border border-slate-200"
      >
        🙋 请求 AI 答疑
      </button>

      <button
        onClick={onRun}
        disabled={isRunning}
        className="px-4 py-2.5 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors cursor-pointer flex items-center gap-1.5 shadow-sm"
      >
        {isFixedCase ? '🚀 提交评测' : '🚀 运行代码'}
      </button>
    </div>
  );
}

export default function CodeSandboxCard({
  problem_id: problemId,
  question_text,
  code: legacyCode,
  language,
  default_stdin
}) {
  const { sendMessage, isSending } = useChat();
  const { problem, error, isLoading } = useCodeProblem(problemId);
  const isFixedCaseProblem = Boolean(problemId);
  const [selectedLanguage, setSelectedLanguage] = useState(language || 'python');

  useEffect(() => {
    if (problem?.language) {
      setSelectedLanguage(problem.language);
    } else if (language) {
      setSelectedLanguage(language);
    }
  }, [problem?.language, language]);

  const displayLanguage = problem?.language || selectedLanguage;
  const initialStarter = problem?.starter_code || legacyCode || defaultTemplates[displayLanguage] || '';

  const {
    code, setCode, stdin, setStdin, isRunning, result, runCode
  } = useCodeSandboxExecution({
    initialCode: initialStarter,
    defaultStdin: default_stdin,
    language: displayLanguage,
    problemId
  });

  const handleLanguageChange = (newLang) => {
    setSelectedLanguage(newLang);
    const currentCodeClean = code.trim();
    const isTemplate = Object.values(defaultTemplates).some(t => t.trim() === currentCodeClean) || currentCodeClean === '';
    if (isTemplate) {
      setCode(defaultTemplates[newLang] || '');
    }
  };

  const handleAskAI = () => {
    if (!isSending) {
      sendMessage(buildAskAIPrompt({ code, language: displayLanguage, stdin, result }));
    }
  };

  if (isLoading) return <div className="p-4 text-sm text-slate-500">正在加载代码题...</div>;
  if (error || (isFixedCaseProblem && !problem)) {
    return <div className="p-4 text-sm text-rose-600">代码题加载失败或已不可访问。</div>;
  }

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col h-full space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h3 className="text-slate-800 font-bold text-base flex items-center gap-2">
          <span>💻 交互式编程沙箱</span>
        </h3>
        <LanguageSelector
          isFixedCase={isFixedCaseProblem}
          currentLanguage={displayLanguage}
          onLanguageChange={handleLanguageChange}
        />
      </div>

      <div className="bg-slate-50 border border-slate-150 rounded-xl p-4 text-slate-700 text-sm leading-relaxed">
        <p className="font-semibold text-slate-800 mb-2 text-xs">题目要求：</p>
        <MarkdownViewer content={problem?.statement || question_text} className="text-slate-700 bg-transparent p-0 border-0" />
        <PublicTestCases cases={problem?.public_cases} />
      </div>

      <CodeEditor displayLanguage={displayLanguage} code={code} onCodeChange={setCode} />
      <StdinInput isFixedCase={isFixedCaseProblem} stdin={stdin} onStdinChange={setStdin} />
      <CodeSandboxConsole result={result} isRunning={isRunning} />
      <ActionButtons
        isSending={isSending}
        isRunning={isRunning}
        isFixedCase={isFixedCaseProblem}
        onAskAI={handleAskAI}
        onRun={runCode}
      />
    </div>
  );
}
