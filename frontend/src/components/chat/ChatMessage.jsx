import ToolCallCard from './ToolCallCard';
import { extractModelText } from '../../utils/chatContent';
import Icon from '../Icon';
import MarkdownViewer from '../common/MarkdownViewer';

const PLAN_STATUS_META = {
  pending: { label: '待执行', className: 'bg-slate-100 text-slate-600 border-slate-200' },
  in_progress: { label: '进行中', className: 'bg-cyan-50 text-cyan-700 border-cyan-200' },
  completed: { label: '完成', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  deleted: { label: '已删除', className: 'bg-slate-100 text-slate-400 border-slate-200' }
};

const SAFETY_STATUS_META = {
  flag: { label: '内容安全提示', className: 'border-amber-200 bg-amber-50 text-amber-700', icon: 'shield_alert' },
  block: { label: '回答已终止', className: 'border-red-200 bg-red-50 text-red-700', icon: 'gpp_bad' }
};

function PlanTaskList({ tasks = [] }) {
  return (
    <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3 text-[12px] text-slate-700 shadow-sm">
      <div className="mb-2 flex items-center gap-2 font-semibold text-slate-800">
        <Icon name="list_alt" className="text-[15px] text-indigo-600" />
        <span>AI 计划</span>
      </div>
      <div className="space-y-2">
        {tasks.map((task) => {
          const meta = PLAN_STATUS_META[task.status] || PLAN_STATUS_META.pending;
          return (
            <div key={task.id} className="rounded-lg border border-white/70 bg-white/80 px-2.5 py-2">
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-slate-800">{task.title}</span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${meta.className}`}>
                  {meta.label}
                </span>
              </div>
              {task.description && (
                <div className="mt-1 leading-relaxed text-slate-500">{task.description}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ContentSafetyNotice({ review }) {
  if (!review || review.action === 'allow') return null;
  const meta = SAFETY_STATUS_META[review.action] || SAFETY_STATUS_META.flag;
  const reason = review.action === 'block'
    ? '检测到内容安全风险，回答已自动终止。'
    : review.reason;
  return (
    <div className={`rounded-lg border px-3 py-2 text-[12px] leading-relaxed ${meta.className}`}>
      <div className="flex items-center gap-1.5 font-semibold">
        <Icon name={meta.icon} className="text-[15px]" />
        <span>{meta.label}</span>
      </div>
      {reason && <div className="mt-1">{reason}</div>}
    </div>
  );
}

export default function ChatMessage({ message, onSendMessage, onRegenerate, isLastAssistant = false }) {
  const isUser = message.role === 'user';
  const isReviewFlagged = !isUser && message.reviewFlagged;
  const isSafetyBlocked = !isUser && message.safetyBlocked;
  const canUseAssistantActions = !isUser && !message.loading && !isSafetyBlocked;
  const hasOrderedParts = !isUser && Array.isArray(message.parts) && message.parts.length > 0;

  const handleCopy = () => {
    navigator.clipboard?.writeText(typeof message.content === 'string' ? message.content : '').catch(console.error);
  };
  
  return (
    <div className={`flex gap-3 max-w-[100%] min-w-0 group ${isUser ? 'ml-auto flex-row-reverse' : ''} ${isReviewFlagged ? 'opacity-60' : ''}`}>
      <div className={`w-8 h-8 flex-shrink-0 flex items-center justify-center mt-1 ${isUser ? 'bg-transparent text-slate-400' : 'rounded-full bg-gradient-to-tr from-cyan-400 to-indigo-400 text-white shadow-sm'}`}>
        {isUser ? (
          <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center text-slate-500"><Icon name="person" className="text-[14px]"/></div>
        ) : (
          <span className="text-[11px] font-bold tracking-wider">AI</span>
        )}
      </div>
      
      <div className={`w-full min-w-0 overflow-hidden transition-all ${isUser ? 'bg-cyan-500 text-white rounded-lg rounded-tr-sm shadow-md p-3.5 max-w-[85%]' : 'text-slate-700 py-2 px-1'}`}>
        
        {/* Tool Calls */}
        {!isUser && !hasOrderedParts && message.toolCalls && message.toolCalls.map((tc, idx) => (
          <ToolCallCard key={idx} name={tc.name} status={tc.status} />
        ))}

        {isReviewFlagged && (
          <div className="mb-2 flex w-fit items-center gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700">
            <Icon name="warning" className="material-symbols-outlined text-[15px]"/>
            该回答可能不准确
          </div>
        )}

        {/* Markdown Content */}
        {isSafetyBlocked ? (
          <div className="space-y-3">
            <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-[13px] font-medium text-red-700">
              抱歉，我无法回答你的问题。
            </div>
            <ContentSafetyNotice review={message.safetyReview} />
          </div>
        ) : hasOrderedParts ? (
          <div className="space-y-3">
            {message.parts.map((part, idx) => {
              if (part.type === 'plan') {
                return <PlanTaskList key={`part-plan-${idx}`} tasks={part.tasks} />;
              }
              if (part.type === 'content_safety_review') {
                return <ContentSafetyNotice key={`part-safety-${idx}`} review={part.review} />;
              }
              if (part.type === 'tool') {
                const toolCall = part.toolCall || {};
                const hasPlanPart = message.parts.some(p => p.type === 'plan');
                const isPlanningTool = ['TaskCreate', 'TaskUpdate', 'TaskList', 'TaskGet'].includes(toolCall.name);
                if (hasPlanPart && isPlanningTool) {
                  return null;
                }
                return (
                  <ToolCallCard
                    key={`part-tool-${toolCall.id || idx}`}
                    name={toolCall.name}
                    title={toolCall.title}
                    status={toolCall.status}
                    description={toolCall.description}
                    inputSummary={toolCall.inputSummary}
                    outputSummary={toolCall.outputSummary}
                  />
                );
              }
              return (
                <div key={`part-text-${idx}`} className="markdown-body break-words leading-[1.65] text-slate-700 text-[13px]">
                  <MarkdownViewer
                    content={extractModelText(part.content || '')}
                    className="text-slate-700 text-[13px]"
                    loading={message.loading}
                    compact
                  />
                </div>
              );
            })}
          </div>
        ) : (
          <div className={`markdown-body break-words leading-[1.65] ${isUser ? 'text-white text-[13px]' : 'text-slate-700 text-[13px]'}`}>
            <MarkdownViewer
              content={extractModelText(message.content)}
              className={isUser ? 'text-white text-[13px]' : 'text-slate-700 text-[13px]'}
              loading={message.loading}
              compact={!isUser}
            />
          </div>
        )}

        {/* Loading Indicator */}
        {message.loading && message.content === '' && !hasOrderedParts && (
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
            loading={message.loading}
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
