import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from '../../utils/mermaid';
import { sanitizeMermaidSource } from '../../utils/mermaid';
import Icon from '../Icon';

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

      let renderId = '';
      try {
        renderId = `chat-mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        console.log('[MERMAID_RAW:viewer]', renderId, source);
        const result = await mermaid.render(renderId, source);
        if (result.svg.includes('error in text')) {
          console.warn('[MERMAID_ERROR] "error in text" detected', { renderId, source });
          throw new Error('Mermaid syntax error');
        }
        if (result.svg.length < 200) {
          console.warn('[MERMAID_WARN] SVG unusually small — possible partial render', {
            renderId, svgLength: result.svg.length, svgPreview: result.svg.slice(0, 300)
          });
        }
        if (!cancelled) {
          setSvg(result.svg);
          setError('');
        }
      } catch (err) {
        console.warn('Mermaid render failed, showing source:', err?.message);
        if (!cancelled) {
          setSvg('');
          setError('fallback');
        }
      } finally {
        if (renderId) {
          document.getElementById(renderId)?.remove();
          document.getElementById(`d${renderId}`)?.remove();
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
      <pre className="text-xs p-3 bg-slate-100 rounded-lg overflow-x-auto font-mono text-slate-600 border border-slate-200 whitespace-pre-wrap">{source}</pre>
    );
  }

  if (!svg) {
    return <div className="text-slate-400 text-xs py-4 text-center">正在生成可视化图解...</div>;
  }

  return <div className="mermaid-svg-wrapper overflow-x-auto p-2 bg-white rounded-lg border border-slate-100 shadow-inner" dangerouslySetInnerHTML={{ __html: svg }} />;
}

export default function MarkdownViewer({ content, className = '' }) {
  const handleCopy = (text) => {
    navigator.clipboard?.writeText(text).catch(console.error);
  };

  return (
    <div className={`markdown-body break-words leading-[1.7] ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className: codeClassName, children, ...rest }) {
            const match = /language-(\w+)/.exec(codeClassName || '');
            const codeStr = String(children).replace(/\n$/, '');
            
            if (!inline && match) {
              if (match[1] === 'mermaid') {
                return (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm">
                    <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
                      <Icon name="schema" className="material-symbols-outlined text-[16px] text-cyan-600"/>
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
                      <Icon name="content_copy" className="material-symbols-outlined text-[14px]"/>
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
              <code {...rest} className={`${codeClassName || ''} bg-slate-100 text-cyan-700 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-200`.trim()}>
                {children}
              </code>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
