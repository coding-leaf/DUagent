import React, { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid, { sanitizeMermaidSource, getCachedSvg, setCachedSvg } from '../../utils/mermaid';
import Icon from '../Icon';
import { useChat } from '../../context/ChatContext';
import { markdownHeadingId } from '../../utils/markdownAnchors';


class MermaidErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[MermaidErrorBoundary] Render error caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <pre className="text-xs p-3 bg-slate-100 rounded-lg overflow-x-auto font-mono text-slate-600 border border-slate-200 whitespace-pre-wrap">
          {this.props.fallbackContent}
        </pre>
      );
    }
    return this.props.children;
  }
}

function MermaidDiagram({ content }) {
  const source = sanitizeMermaidSource(content);
  const [viewMode, setViewMode] = useState('fit');
  const [svg, setSvg] = useState(() => {
    const cached = getCachedSvg(source);
    return (cached && cached !== '__FAILED_FALLBACK__') ? cached : '';
  });
  const [error, setError] = useState(() => {
    const cached = getCachedSvg(source);
    return cached === '__FAILED_FALLBACK__' ? 'fallback' : '';
  });

  useEffect(() => {
    let cancelled = false;

    const renderDiagram = async () => {
      if (!source) {
        setSvg('');
        setError('');
        return;
      }

      // Direct sync cache hit check
      const cached = getCachedSvg(source);
      if (cached) {
        if (!cancelled) {
          if (cached === '__FAILED_FALLBACK__') {
            setSvg('');
            setError('fallback');
          } else {
            setSvg(cached);
            setError('');
          }
        }
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

        // Cache the successful SVG render output
        setCachedSvg(source, result.svg);

        if (!cancelled) {
          setSvg(result.svg);
          setError('');
        }
      } catch (err) {
        console.warn('Mermaid render failed, showing source:', err?.message);
        // Cache the failed state to avoid repeated render attempts
        setCachedSvg(source, '__FAILED_FALLBACK__');
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

  const viewBoxWidth = Number(svg.match(/\bviewBox=["']\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)/i)?.[1]);
  const originalWidth = Number.isFinite(viewBoxWidth) ? Math.max(viewBoxWidth, 640) : 960;

  return (
    <div className="mermaid-svg-wrapper overflow-hidden rounded-lg border border-slate-100 bg-white shadow-inner">
      <div className="flex justify-end gap-1 border-b border-slate-100 bg-slate-50/80 p-1.5">
        {[
          { value: 'fit', label: '适应窗口' },
          { value: 'original', label: '原始大小' }
        ].map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={viewMode === option.value}
            onClick={() => setViewMode(option.value)}
            className={`cursor-pointer rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 ${
              viewMode === option.value
                ? 'bg-white text-cyan-700 shadow-sm'
                : 'text-slate-500 hover:bg-white hover:text-slate-700'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div
        data-testid="mermaid-viewport"
        data-view-mode={viewMode}
        className="max-h-[32rem] overflow-auto p-2"
      >
        <div
          className="[&_svg]:!block [&_svg]:!h-auto [&_svg]:!max-w-full [&_svg]:!w-full"
          style={viewMode === 'original' ? { width: `${originalWidth}px`, maxWidth: 'none' } : undefined}
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  );
}

const handleCopy = (text) => {
  navigator.clipboard?.writeText(text).catch(console.error);
};

export default function MarkdownViewer({ content, className = '', compact = false, loading = false }) {
  const chat = useChat();
  const activeSession = chat?.activeSession;
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

  const components = useMemo(() => ({
    h1({ children, ...rest }) {
      return <h1 id={markdownHeadingId(children)} {...rest}>{children}</h1>;
    },
    h2({ children, ...rest }) {
      return <h2 id={markdownHeadingId(children)} {...rest}>{children}</h2>;
    },
    h3({ children, ...rest }) {
      return <h3 id={markdownHeadingId(children)} {...rest}>{children}</h3>;
    },
    h4({ children, ...rest }) {
      return <h4 id={markdownHeadingId(children)} {...rest}>{children}</h4>;
    },
    h5({ children, ...rest }) {
      return <h5 id={markdownHeadingId(children)} {...rest}>{children}</h5>;
    },
    h6({ children, ...rest }) {
      return <h6 id={markdownHeadingId(children)} {...rest}>{children}</h6>;
    },
    a({ href, children, ...rest }) {
      if (href && href.startsWith('./') && activeSession) {
        const filename = decodeURIComponent(href.slice(2));
        const token = localStorage.getItem('access_token');
        const downloadUrl = `${apiBaseUrl}/tutoring/conversations/${activeSession}/files/${encodeURIComponent(filename)}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
        return (
          <a
            href={downloadUrl}
            download={filename}
            className="text-cyan-600 hover:text-cyan-700 font-semibold underline inline-flex items-center gap-1 transition-colors"
            {...rest}
          >
            <Icon name="download" className="text-sm shrink-0" />
            {children}
          </a>
        );
      }
      if (href?.startsWith('#')) {
        return (
          <a
            href={href}
            className="text-cyan-600 hover:text-cyan-700 underline transition-colors"
            {...rest}
          >
            {children}
          </a>
        );
      }
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-600 hover:text-cyan-700 underline transition-colors"
          {...rest}
        >
          {children}
        </a>
      );
    },
    code({ inline, className: codeClassName, children, ...rest }) {
      const match = /language-(\w+)/.exec(codeClassName || '');
      const codeStr = String(children).replace(/\n$/, '');
      
      if (!inline && match) {
        if (match[1] === 'mermaid') {
          if (loading) {
            return (
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm animate-pulse">
                <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
                  <Icon name="schema" className="material-symbols-outlined text-[16px] text-cyan-600"/>
                  <span>正在生成可视化图解...</span>
                </div>
                <pre className="text-xs p-3 bg-slate-100 rounded-lg overflow-x-auto font-mono text-slate-600 border border-slate-200 whitespace-pre-wrap">{codeStr}</pre>
              </div>
            );
          }
          return (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm">
              <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
                <Icon name="schema" className="material-symbols-outlined text-[16px] text-cyan-600"/>
                <span>图解模式 (Mermaid)</span>
              </div>
              <MermaidErrorBoundary fallbackContent={codeStr}>
                <MermaidDiagram content={codeStr} />
              </MermaidErrorBoundary>
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
              wrapLongLines={compact}
              customStyle={{
                margin: 0,
                padding: compact ? '0.75rem' : '1rem',
                borderTopLeftRadius: 0,
                borderTopRightRadius: 0,
                fontSize: compact ? '11px' : '13px',
                lineHeight: compact ? '1.45' : '1.5',
                maxWidth: '100%',
                overflowX: compact ? 'hidden' : 'auto',
                whiteSpace: compact ? 'pre-wrap' : 'pre',
                overflowWrap: compact ? 'anywhere' : 'normal'
              }}
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
  }), [activeSession, apiBaseUrl, compact, loading]);

  return (
    <div className={`markdown-body break-words leading-[1.7] ${compact ? 'chat-compact-markdown' : ''} ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
