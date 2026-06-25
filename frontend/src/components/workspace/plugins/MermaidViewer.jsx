import { useEffect, useState } from 'react';
import mermaid, { sanitizeMermaidSource } from '../../../utils/mermaid';

export default function MermaidViewer({ chart }) {
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState(null);
  const source = sanitizeMermaidSource(chart);

  useEffect(() => {
    let cancelled = false;

    const renderDiagram = async () => {
      if (!source) {
        setSvgContent('');
        setError(null);
        return;
      }

      let renderId = '';
      try {
        renderId = `workspace-mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const result = await mermaid.render(renderId, source);
        if (result.svg.includes('error in text')) {
          throw new Error('Mermaid syntax error');
        }
        if (!cancelled) {
          setSvgContent(result.svg);
          setError(null);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (!cancelled) {
          setSvgContent('');
          setError(err);
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
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-red-800 shadow-sm text-sm w-full">
        <h4 className="font-semibold mb-2">Mermaid 图表渲染失败</h4>
        <pre className="text-xs p-3 bg-red-100 rounded-lg overflow-x-auto font-mono text-red-700 border border-red-200 whitespace-pre-wrap">
          {source}
        </pre>
      </div>
    );
  }

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 flex justify-center overflow-x-auto shadow-sm w-full">
      {svgContent ? (
        <div 
          className="mermaid w-full text-center" 
          dangerouslySetInnerHTML={{ __html: svgContent }} 
        />
      ) : (
        <div className="text-slate-400 text-xs py-4 text-center">正在加载图解...</div>
      )}
    </div>
  );
}
