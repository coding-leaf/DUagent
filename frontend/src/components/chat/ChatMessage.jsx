import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from 'mermaid';
import ToolCallCard from './ToolCallCard';

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'strict',
  theme: 'default',
});

const normalizeMermaidSource = (content) => {
  const trimmed = (content || '').trim();
  const fenced = trimmed.match(/^```(?:mermaid)?\s*([\s\S]*?)```$/i);
  return fenced ? fenced[1].trim() : trimmed;
};

const sanitizeMermaidSource = (content) => {
  let source = normalizeMermaidSource(content);
  // 1. [label] -> ["label"]
  source = source.replace(/(\w+)\s*\[([^"\n\]]+)\]/g, '$1["$2"]');
  // 2. ((label)) -> (("label"))
  source = source.replace(/(\w+)\s*\(\(([^"\n)]+)\)\)/g, '$1(("$2"))');
  // 3. (label) -> ("label")
  source = source.replace(/(\w+)\s*\(([^"\n)]+)\)/g, '$1("$2")');
  // 4. {label} -> {"label"}
  source = source.replace(/(\w+)\s*\{([^"\n}]+)\}/g, '$1{"$2"}');
  // 5. >label] -> >"label"]
  source = source.replace(/(\w+)\s*>\s*([^"\n\]]+)\]/g, '$1>"$2"]');
  return source;
};

function MermaidDiagram({ content }) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const source = sanitizeMermaidSource(content);

  useEffect(() => {
    let cancelled = false;

    const renderDiagram = async () => {
      if (!source) {
        setSvg('');
        setError('');
        return;
      }

      try {
        const id = `chat-mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const result = await mermaid.render(id, source);
        if (!cancelled) {
          setSvg(result.svg);
          setError('');
        }
      } catch (err) {
        console.error('Mermaid render failed in ChatMessage:', err);
        if (!cancelled) {
          setSvg('');
          setError('图解渲染失败，已显示原始内容。');
        }
      }
    };

    renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [source]);

  if (error) {
    return (
      <div>
        <div className="text-red-500 text-xs mb-2">{error}</div>
        <pre className="text-xs p-3 bg-slate-100 rounded-lg overflow-x-auto font-mono text-slate-600 border border-slate-200">{source}</pre>
      </div>
    );
  }

  if (!svg) {
    return <div className="text-slate-400 text-xs py-4 text-center">正在生成可视化图解...</div>;
  }

  return <div className="mermaid-svg-wrapper overflow-x-auto p-2 bg-white rounded-lg border border-slate-100 shadow-inner" dangerouslySetInnerHTML={{ __html: svg }} />;
}

const getDisplayText = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') {
    if (value.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(value);
        if (parsed.model_text || parsed.content) {
          return parsed.model_text || parsed.content;
        }
      } catch {
        // Ignored
      }
    }
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.model_text || value.code || value.name || value.title || value.content || JSON.stringify(value);
  }
  return String(value);
};

export default function ChatMessage({ message, onSendMessage }) {
  const isUser = message.role === 'user';
  const isReviewFlagged = !isUser && message.reviewFlagged;
  
  const handleCopy = (text) => {
    navigator.clipboard?.writeText(text).catch(console.error);
  };

  return (
    <div className={`flex gap-4 max-w-[100%] group ${isUser ? 'ml-auto flex-row-reverse' : ''} ${isReviewFlagged ? 'opacity-60' : ''}`}>
      <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center mt-1 ${isUser ? 'bg-cyan-600 text-white shadow-sm' : 'bg-sky-100 text-cyan-600'}`}>
        {isUser ? (
          <span className="material-symbols-outlined text-[18px]">person</span>
        ) : (
          <span className="text-[12px] font-bold">AI</span>
        )}
      </div>
      
      <div className={`w-full transition-all ${isUser ? 'bg-cyan-600 text-white rounded-2xl rounded-tr-none shadow-md p-4 max-w-[85%]' : 'text-slate-700 py-1'}`}>
        
        {/* Tool Calls */}
        {!isUser && message.toolCalls && message.toolCalls.map((tc, idx) => (
          <ToolCallCard key={idx} name={tc.name} status={tc.status} />
        ))}

        {isReviewFlagged && (
          <div className="mb-2 flex w-fit items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
            <span className="material-symbols-outlined text-[15px]">warning</span>
            该回答可能不准确
          </div>
        )}

        {/* Markdown Content */}
        <div className={`markdown-body break-words leading-[1.7] ${isUser ? 'text-white' : 'text-slate-700 text-[15px]'}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({inline, className, children, ...props}) {
                const match = /language-(\w+)/.exec(className || '');
                const codeStr = String(children).replace(/\n$/, '');
                return !inline && match ? (
                  <div className="relative rounded-xl overflow-hidden my-4 group/code shadow-sm border border-slate-200">
                    <div className="flex items-center justify-between px-4 py-2 bg-slate-50 text-slate-500 text-[11px] font-mono uppercase tracking-wider border-b border-slate-200">
                      <span>{match[1]}</span>
                      <button 
                        onClick={() => handleCopy(codeStr)}
                        className="opacity-0 group-hover/code:opacity-100 focus:opacity-100 transition-opacity hover:text-slate-700 flex items-center gap-1 cursor-pointer"
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
                  <code {...props} className={`${className || ''} bg-slate-100 text-cyan-700 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-200`.trim()}>
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
          <div className="flex items-center gap-1.5 text-cyan-500 h-6 pl-1 mt-2">
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
            <span className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
          </div>
        )}

        {/* Error message */}
        {message.isError && (
          <div className="mt-2 text-red-500 text-[13px] flex items-center gap-1 font-medium bg-red-50 p-2 rounded-lg w-fit">
            <span className="material-symbols-outlined text-[16px]">error</span>
            {message.content?.includes('发送失败') ? '' : '生成失败，请重试'}
          </div>
        )}

        {/* Diagrams */}
        {!isUser && message.diagrams && message.diagrams.map((diag, index) => (
          <div key={`diagram-${index}`} className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm">
            <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
              <span className="material-symbols-outlined text-[16px] text-cyan-600">schema</span>
              <span>图解模式 (Mermaid)</span>
            </div>
            <MermaidDiagram content={getDisplayText(diag)} />
          </div>
        ))}

        {/* Suggestions */}
        {!isUser && message.suggestions && message.suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-slate-100">
            {message.suggestions.map((sug, i) => (
              <button
                key={`suggestion-${i}`}
                onClick={() => onSendMessage(sug)} 
                className="px-3 py-1.5 bg-white text-slate-600 text-[13px] rounded-lg cursor-pointer hover:bg-slate-50 transition-all border border-slate-200 shadow-sm flex items-center gap-1.5 active:scale-95"
              >
                <span className="material-symbols-outlined text-[14px] text-cyan-500">lightbulb</span>
                {sug}
              </button>
            ))}
          </div>
        )}

        {/* Knowledge Points */}
        {!isUser && message.knowledge_points && message.knowledge_points.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 items-center">
            {message.knowledge_points.map((kp, i) => (
              <span key={`kp-${i}`} className="px-2.5 py-1 bg-slate-100 text-slate-600 text-[12px] rounded-md font-medium">
                # {kp}
              </span>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
