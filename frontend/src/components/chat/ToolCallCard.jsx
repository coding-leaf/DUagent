import { useState } from 'react';

export default function ToolCallCard({ name, status, details }) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = status === 'running';

  return (
    <div className="bg-white border border-gray-100 rounded-xl mb-4 overflow-hidden text-sm max-w-xl shadow-sm">
      <div 
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {isRunning ? (
             <span className="material-symbols-outlined animate-spin text-cyan-600 text-lg">progress_activity</span>
          ) : (
             <span className="material-symbols-outlined text-emerald-500 text-lg">check_circle</span>
          )}
          <span className={`font-medium ${isRunning ? 'text-gray-700' : 'text-gray-500'}`}>
            {name || '正在执行工具...'}
          </span>
        </div>
        <span className={`material-symbols-outlined text-gray-400 transition-transform duration-300 ${expanded ? 'rotate-180' : ''}`}>
          expand_more
        </span>
      </div>
      
      <div 
        className={`transition-all duration-300 ease-in-out ${expanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'}`}
      >
        {details && (
          <div className="px-4 pb-4 pt-1 text-[13px] text-gray-500 font-mono whitespace-pre-wrap overflow-y-auto max-h-80">
            {details}
          </div>
        )}
      </div>
    </div>
  );
}
