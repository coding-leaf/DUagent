import ToolCallCard from './ToolCallCard';
import { extractModelText } from '../../utils/chatContent';
import Icon from '../Icon';
import MarkdownViewer from '../common/MarkdownViewer';

export default function ChatMessage({ message, onSendMessage, onRegenerate, isLastAssistant = false }) {
  const isUser = message.role === 'user';
  const isReviewFlagged = !isUser && message.reviewFlagged;
  const canUseAssistantActions = !isUser && !message.loading;

  const handleCopy = () => {
    navigator.clipboard?.writeText(typeof message.content === 'string' ? message.content : '').catch(console.error);
  };
  
  return (
    <div className={`flex gap-3 max-w-[100%] min-w-0 group ${isUser ? 'ml-auto flex-row-reverse' : ''} ${isReviewFlagged ? 'opacity-60' : ''}`}>
      <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center mt-1 ${isUser ? 'bg-cyan-600 text-white shadow-sm' : 'bg-sky-100 text-cyan-600'}`}>
        {isUser ? (
          <Icon name="person" className="material-symbols-outlined text-[18px]"/>
        ) : (
          <span className="text-[12px] font-bold">AI</span>
        )}
      </div>
      
      <div className={`w-full min-w-0 overflow-hidden transition-all ${isUser ? 'bg-cyan-600 text-white rounded-2xl rounded-tr-none shadow-md p-3 max-w-[85%]' : 'text-slate-700 py-1'}`}>
        
        {/* Tool Calls */}
        {!isUser && message.toolCalls && message.toolCalls.map((tc, idx) => (
          <ToolCallCard key={idx} name={tc.name} status={tc.status} />
        ))}

        {isReviewFlagged && (
          <div className="mb-2 flex w-fit items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
            <Icon name="warning" className="material-symbols-outlined text-[15px]"/>
            该回答可能不准确
          </div>
        )}

        {/* Markdown Content */}
        <div className={`markdown-body break-words leading-[1.65] ${isUser ? 'text-white text-[13px]' : 'text-slate-700 text-[13px]'}`}>
          <MarkdownViewer 
            content={extractModelText(message.content)} 
            className={isUser ? 'text-white text-[13px]' : 'text-slate-700 text-[13px]'} 
            compact={!isUser}
          />
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
            <Icon name="error" className="material-symbols-outlined text-[16px]"/>
            {message.content?.includes('发送失败') ? '' : '生成失败，请重试'}
          </div>
        )}

        {canUseAssistantActions && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
            {isLastAssistant && (
              <button
                onClick={onRegenerate}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 shadow-sm transition-colors hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
              >
                <Icon name="refresh" className="text-[14px]" />
                重新生成
              </button>
            )}
            <button
              onClick={() => onSendMessage('请继续细化这次生成的内容。')}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 shadow-sm transition-colors hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
            >
              <Icon name="tune" className="text-[14px]" />
              继续细化
            </button>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 shadow-sm transition-colors hover:border-cyan-200 hover:bg-cyan-50 hover:text-cyan-700"
            >
              <Icon name="content_copy" className="text-[14px]" />
              复制
            </button>
          </div>
        )}

        {/* Diagrams */}
        {!isUser && message.diagrams && message.diagrams.map((diag, index) => (
          <MarkdownViewer 
            key={`diagram-${index}`}
            content={`\`\`\`mermaid\n${extractModelText(diag)}\n\`\`\``} 
          />
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
                <Icon name="lightbulb" className="material-symbols-outlined text-[14px] text-cyan-500"/>
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
