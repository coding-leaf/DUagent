import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
});

export default function MermaidViewer({ chart }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current && chart) {
      containerRef.current.innerHTML = chart;
      try {
        mermaid.contentLoaded();
      } catch (err) {
        console.error('Mermaid render error:', err);
      }
    }
  }, [chart]);

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 flex justify-center overflow-x-auto shadow-sm">
      <div ref={containerRef} className="mermaid w-full text-center" />
    </div>
  );
}
