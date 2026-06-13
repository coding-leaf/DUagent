
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ToolCallCard from './ToolCallCard';

const getDisplayText = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.code || value.name || value.title || value.content || JSON.stringify(value);
  }
  return String(value);
};

export default function ChatMessage({ message, onSendMessage }) {
  const isUser = message.role === 'user';
  
  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className={`flex gap-4 max-w-[85%] group ${isUser ? 'ml-auto flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-1 ${isUser ? 'bg-cyan-600 text-white shadow-sm' : 'bg-gradient-to-tr from-cyan-100 to-emerald-50 text-cyan-700 shadow-sm border border-cyan-100'}`}>
        <span className="material-symbols-outlined text-[18px]" style={!isUser ? { fontVariationSettings: '"FILL" 1' } : {}}>
          {isUser ? 'person' : 'smart_toy'}
        </span>
      </div>
      
      <div className={`p-4 rounded-2xl w-full transition-all ${isUser ? 'bg-cyan-600 text-white rounded-tr-none shadow-md' : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none shadow-sm hover:shadow-md'}`}>
        
        {/* Tool Calls (if any) */}
        {!isUser && message.toolCalls && message.toolCalls.map((tc, idx) => (
          <ToolCallCard key={idx} name={tc.name} status={tc.status} details={tc.details} />
        ))}

        {/* Content using Markdown */}
        <div className={`markdown-body break-words ${isUser ? 'text-white' : 'text-gray-800'}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({inline, className, children, ...props}) {
                const match = /language-(\w+)/.exec(className || '');
                const codeStr = String(children).replace(/\n$/, '');
                return !inline && match ? (
                  <div className="relative rounded-lg overflow-hidden my-4 group/code shadow-sm border border-gray-700">
                    <div className="flex items-center justify-between px-4 py-2 bg-gray-900 text-gray-400 text-[11px] font-mono uppercase tracking-wider">
                      <span>{match[1]}</span>
                      <button 
                        onClick={() => handleCopy(codeStr)}
                        className="opacity-0 group-hover/code:opacity-100 transition-opacity hover:text-white flex items-center gap-1 cursor-pointer"
                        title="Copy code"
                      >
                        <span className="material-symbols-outlined text-[14px]">content_copy</span>
                        Copy
                      </button>
                    </div>
                    <SyntaxHighlighter
                      {...props}
                      children={codeStr}
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      customStyle={{ margin: 0, padding: '1rem', borderTopLeftRadius: 0, borderTopRightRadius: 0, fontSize: '13px', lineHeight: '1.5' }}
                    />
                  </div>
                ) : (
                  <code {...props} className={`${className} bg-gray-100 text-cyan-700 px-1.5 py-0.5 rounded text-[13px] font-mono border border-gray-200`}>
                    {children}
                  </code>
                );
              }
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Loading Indicator */}
        {message.loading && message.content === '' && (
          <div className="flex items-center gap-1.5 text-cyan-500 h-6 pl-1">
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
          </div>
        )}

        {/* Error message */}
        {message.isError && (
          <div className="mt-2 text-red-500 text-[13px] flex items-center gap-1 font-medium bg-red-50 p-2 rounded-lg">
            <span className="material-symbols-outlined text-[16px]">error</span>
            {message.content.includes('发送失败') ? '' : '生成失败，请重试'}
          </div>
        )}

        {/* Diagrams rendering */}
        {!isUser && message.diagrams && message.diagrams.map((diag, index) => (
          <div key={`diagram-${index}`} className="bg-gray-50 rounded-xl p-4 border border-gray-200 mt-4 mb-2 shadow-sm">
            <div className="flex items-center gap-2 mb-2 text-xs text-gray-500 font-medium uppercase tracking-wide">
              <span className="material-symbols-outlined text-[16px] text-cyan-600">schema</span>
              <span>图解模式 (Mermaid)</span>
            </div>
            <pre className="text-[13px] font-mono bg-[#1E1E1E] text-slate-100 p-4 rounded-lg overflow-x-auto whitespace-pre border border-gray-800 leading-relaxed">
              {getDisplayText(diag)}
            </pre>
          </div>
        ))}

        {/* Suggestions rendering */}
        {!isUser && message.suggestions && message.suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-gray-100">
            {message.suggestions.map((sug, i) => (
              <button
                key={`suggestion-${i}`}
                onClick={() => onSendMessage(sug)} 
                className="px-3 py-1.5 bg-white text-cyan-700 text-[13px] rounded-lg cursor-pointer hover:bg-cyan-50 transition-all border border-cyan-100 shadow-sm flex items-center gap-1.5 active:scale-95 hover:shadow hover:border-cyan-200"
              >
                <span className="material-symbols-outlined text-[14px] text-yellow-500">lightbulb</span>
                {sug}
              </button>
            ))}
          </div>
        )}

        {/* Knowledge Points Badges */}
        {!isUser && message.knowledge_points && message.knowledge_points.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-gray-100 items-center">
            <span className="text-[12px] text-gray-400 flex items-center gap-1 mr-1 font-medium">
              <span className="material-symbols-outlined text-[16px]">school</span>
              关联知识点
            </span>
            {message.knowledge_points.map((kp, i) => (
              <span key={`kp-${i}`} className="px-2 py-1 bg-emerald-50 text-emerald-700 text-[11px] rounded-md font-medium border border-emerald-100/50 shadow-sm">
                {kp}
              </span>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
