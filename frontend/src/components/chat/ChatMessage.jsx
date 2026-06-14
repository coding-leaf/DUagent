import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from 'mermaid';
import ToolCallCard from './ToolCallCard';
import { extractModelText } from '../../utils/chatContent';

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

  // Define the opening patterns we want to match, ordered by specificity
  const patterns = [
    { open: '((', close: '))', openChar: '(', closeChar: ')' },
    { open: '{{', close: '}}', openChar: '{', closeChar: '}' },
    { open: '[/', close: '/]', openChar: '[', closeChar: ']' },
    { open: '[\\', close: '\\]', openChar: '[', closeChar: ']' },
    { open: '[', close: ']', openChar: '[', closeChar: ']' },
    { open: '(', close: ')', openChar: '(', closeChar: ')' },
    { open: '{', close: '}', openChar: '{', closeChar: '}' },
    { open: '>', close: ']', openChar: '[', closeChar: ']' }
  ];

  // Regexp to find a word boundary, an identifier, optional spaces, and one of the openings
  const escapedOpens = patterns.map(p => p.open.split('').map(c => '\\' + c).join('')).join('|');
  const regex = new RegExp(`\\b(\\w+)\\s*(${escapedOpens})`, 'g');

  let match;
  let lastIndex = 0;
  let result = '';

  while ((match = regex.exec(source)) !== null) {
    const id = match[1];
    const openStr = match[2];
    const matchStart = match.index;
    
    const config = patterns.find(p => p.open === openStr);
    if (!config) {
      result += source.substring(lastIndex, regex.lastIndex);
      lastIndex = regex.lastIndex;
      continue;
    }

    const { close: closeStr, openChar, closeChar } = config;
    
    // Scan forward from regex.lastIndex to find the matching closeStr
    let nesting = 1;
    let i = regex.lastIndex;
    let foundCloseIndex = -1;

    while (i < source.length) {
      if (source.substring(i, i + closeStr.length) === closeStr) {
        nesting--;
        if (nesting === 0) {
          foundCloseIndex = i;
          break;
        }
        i += closeStr.length;
        continue;
      }
      
      // If we see a nested open character
      if (source.charAt(i) === openChar) {
        nesting++;
      } else if (source.charAt(i) === closeChar) {
        nesting--;
        if (nesting === 0) {
          foundCloseIndex = i;
          break;
        }
      }
      i++;
    }

    if (foundCloseIndex !== -1) {
      const labelStart = regex.lastIndex;
      const labelEnd = foundCloseIndex;
      let label = source.substring(labelStart, labelEnd);

      const isQuoted = (label.startsWith('"') && label.endsWith('"')) || (label.startsWith("'") && label.endsWith("'"));
      if (!isQuoted) {
        const escapedLabel = label.replace(/"/g, '\\"');
        label = `"${escapedLabel}"`;
      }

      result += source.substring(lastIndex, matchStart);
      result += `${id}${openStr}${label}${closeStr}`;
      
      lastIndex = foundCloseIndex + closeStr.length;
      regex.lastIndex = lastIndex;
    } else {
      result += source.substring(lastIndex, regex.lastIndex);
      lastIndex = regex.lastIndex;
    }
  }

  result += source.substring(lastIndex);
  return result;
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
              code(codeProps) {
                // eslint-disable-next-line no-unused-vars
                const { inline, className, children, node, ...rest } = codeProps;
                const match = /language-(\w+)/.exec(className || '');
                const codeStr = String(children).replace(/\n$/, '');
                
                if (!inline && match) {
                  if (match[1] === 'mermaid') {
                    return (
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm">
                        <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
                          <span className="material-symbols-outlined text-[16px] text-cyan-600">schema</span>
                          <span>图解模式 (Mermaid)</span>
                        </div>
                        <MermaidDiagram content={codeStr} />
                      </div>
                    );
                  }
                  
                  return (
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
                        {...rest}
                        children={codeStr}
                        style={vscDarkPlus}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{ margin: 0, padding: '1rem', borderTopLeftRadius: 0, borderTopRightRadius: 0, fontSize: '13px', lineHeight: '1.5' }}
                      />
                    </div>
                  );
                }
                
                return (
                  <code {...rest} className={`${className || ''} bg-slate-100 text-cyan-700 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-200`.trim()}>
                    {children}
                  </code>
                );
              }
            }}
          >
            {extractModelText(message.content)}
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
            <MermaidDiagram content={extractModelText(diag)} />
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
