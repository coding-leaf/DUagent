import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useMemo } from 'react';
import Icon from '../../Icon';
import { useChat } from '../../../context/ChatContext';
import { markdownHeadingId } from '../../../utils/markdownAnchors';

const COMPONENTS = {
  h1: ({ children, ...props }) => (
    <h1 id={markdownHeadingId(children)} className="text-2xl font-bold text-slate-800 mt-6 mb-4 pb-2 border-b border-slate-100" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 id={markdownHeadingId(children)} className="text-xl font-semibold text-slate-800 mt-5 mb-3" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 id={markdownHeadingId(children)} className="text-lg font-medium text-slate-800 mt-4 mb-2" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }) => (
    <p className="text-slate-600 leading-relaxed mb-4 text-[14px]" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="list-disc pl-5 mb-4 space-y-1 text-[14px] text-slate-600" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="list-decimal pl-5 mb-4 space-y-1 text-[14px] text-slate-600" {...props}>
      {children}
    </ol>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-500 my-4 bg-slate-50 py-1 pr-2 rounded-r-lg" {...props}>
      {children}
    </blockquote>
  ),
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto my-4 border border-slate-200 rounded-xl w-full">
      <table className="min-w-full divide-y divide-slate-200" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-slate-50" {...props}>
      {children}
    </thead>
  ),
  tbody: ({ children, ...props }) => (
    <tbody className="bg-white divide-y divide-slate-100" {...props}>
      {children}
    </tbody>
  ),
  th: ({ children, ...props }) => (
    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider" {...props}>
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="px-4 py-3 text-sm text-slate-600" {...props}>
      {children}
    </td>
  ),
  code: ({ className, children, ...props }) => {
    const match = /language-(\w+)/.exec(className || '');
    return match ? (
      <pre className="bg-slate-900 text-slate-100 p-4 rounded-xl overflow-x-auto text-sm font-mono my-4 w-full">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    ) : (
      <code className="bg-slate-100 text-pink-600 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</> // Prevent double wrapping with pre
};

export default function MarkdownViewer({ title, content }) {
  const chat = useChat();
  const activeSession = chat?.activeSession;
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const components = useMemo(() => ({
    ...COMPONENTS,
    a({ href, children, ...props }) {
      if (href?.startsWith('./') && activeSession) {
        let filename;
        try {
          filename = decodeURIComponent(href.slice(2));
        } catch {
          filename = href.slice(2);
        }
        const token = localStorage.getItem('access_token');
        const downloadUrl = `${apiBaseUrl}/tutoring/conversations/${activeSession}/files/${encodeURIComponent(filename)}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
        return (
          <a
            href={downloadUrl}
            download={filename}
            className="text-cyan-600 hover:text-cyan-700 font-semibold underline inline-flex items-center gap-1 transition-colors"
            {...props}
          >
            <Icon name="download" className="text-sm shrink-0" />
            {children}
          </a>
        );
      }
      if (href?.startsWith('#')) {
        return (
          <a href={href} className="text-cyan-600 hover:text-cyan-700 underline transition-colors" {...props}>
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
          {...props}
        >
          {children}
        </a>
      );
    }
  }), [activeSession, apiBaseUrl]);

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-6 shadow-sm w-full">
      {title ? (
        <div className="mb-5 border-b border-slate-100 pb-3">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        </div>
      ) : null}
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
