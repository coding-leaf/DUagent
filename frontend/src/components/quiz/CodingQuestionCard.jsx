import CodeSandboxCard from '../workspace/plugins/codeSandbox/CodeSandboxCard';

export default function CodingQuestionCard({ question, value, onChange }) {
  return (
    <div className="bg-white border border-outline-variant rounded-xl p-6 hover:shadow-sm transition-all duration-200">
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[11px] font-medium text-violet-700 bg-violet-50 px-2 py-0.5 rounded-md">
            C 语言在线编程
          </span>
          <span className="text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md">
            实操练习
          </span>
        </div>
        <h3 className="text-title-md font-medium text-on-surface mt-2">
          {question?.title || '编程实践'}
        </h3>
        {question?.description && (
          <p className="text-body-md text-secondary mt-1 whitespace-pre-line">
            {question.description}
          </p>
        )}
      </div>
      
      {/* 载入高级代码判题沙箱 */}
      <CodeSandboxCard 
        problem_id={question?.id} 
        initialCode={value || question?.initial_code || ''}
        onCodeChange={(newCode) => onChange(newCode)} 
        showAskAI={false}
      />
    </div>
  );
}
