import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import Icon from '../Icon';
import { useChat } from '../../context/ChatContext';
import { markdownHeadingId } from '../../utils/markdownAnchors';

const handleCopy = (text) => {
  navigator.clipboard?.writeText(text).catch(console.error);
};

export default function MarkdownViewer({ content, className = '', compact = false }) {
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
  }), [activeSession, apiBaseUrl, compact]);

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
