# AIChat Frontend Audit Report (Modularity, SWR, and MVVM)

This report presents an architectural audit of the frontend `AIChat` workspace, analyzing `frontend/src/pages/AIChat.jsx` and components under `frontend/src/components/chat/` for MVVM compliance, SWR utilization, codebase modularity, code cleanliness, and specific recommended refactoring edits.

---

## 1. Executive Summary
- **Current State**: The AIChat module is divided into a layout container (`AIChat.jsx`), UI presentation components (chat history, resources sidebar, chat message panel), and a unified state provider (`ChatContext.jsx`). 
- **Core Findings**: 
  1. **MVVM Compliance**: Mostly compliant. `ChatContext.jsx` behaves as a robust ViewModel for chat interactions. However, `SidebarResources.jsx` violates the MVVM pattern by directly executing raw API fetching and maintaining its own loading/error state.
  2. **SWR Usage**: Highly deficient. SWR is completely absent in the AIChat stack. The code relies on manual `useEffect` fetching and local `useState` synchronization. This violates the project-scoped rule of prioritizing SWR/React Query for data fetching and caching.
  3. **Code Cleanliness**: The components are clean with no unused imports or extraneous `console.log` statements. However, there are multiple ESLint suppression comments (`eslint-disable-next-line react-hooks/set-state-in-effect`) and hacky `setTimeout` states that should be eliminated via SWR refactoring.

---

## 2. Component Audits

### 2.1 `frontend/src/pages/AIChat.jsx`
- **Role**: View (Page Layout / Container).
- **Modularity**: Excellent. It manages layout drawers/collapses and serves as the structural entry point, delegating all domain logic to `ChatContext` and visual presentation to sub-components.
- **MVVM Compliance**: Fully compliant. It remains a thin UI view with zero data-fetching or state-manipulation logic.
- **SWR Usage**: N/A (Does not retrieve data).
- **Cleanliness**: 100% clean. No unused imports or debug logs.

### 2.2 `frontend/src/components/chat/SidebarHistory.jsx`
- **Role**: View (History Panel).
- **Modularity**: Good. Focuses purely on displaying historical conversations, handling new chat triggers, and deletion actions.
- **MVVM Compliance**: Compliant. It reads history state (`sessions`, `activeSession`) and triggers actions (`deleteSession`, `setActiveSession`) from the `useChat` ViewModel context.
- **SWR/Fetching**: N/A (Delegates to ViewModel).

### 2.3 `frontend/src/components/chat/SidebarResources.jsx`
- **Role**: View (Resource Recommendations Panel).
- **Modularity**: Suboptimal. It contains complex business logic to filter resources based on active knowledge points (`activeKPs`) extracted from the chat messages list.
- **MVVM Compliance**: **Violated**. It manages data state (`resources`), handles manual `useEffect` fetching, traps network errors (`error`), and uses helper state management hacks (like `setTimeout` on unmount to reset resources). This logic belongs in a ViewModel/custom hook.
- **SWR/Fetching**: **Violated**. It uses manual fetch via `learningService.getResources` wrapped in `useEffect` and `useState`.
- **Cleanliness**: Contains a bypass comment `// eslint-disable-next-line react-hooks/set-state-in-effect` and a debug `console.error(err)`.

### 2.4 `frontend/src/components/chat/ChatArea.jsx`
- **Role**: View (Main Chat Workspace).
- **Modularity**: Good. Handles scroll-to-bottom physics (`requestAnimationFrame` + `scrollIntoView`), dynamic textarea height resizing, message editing state (`editingMsg`), and user inputs.
- **MVVM Compliance**: Compliant. Binds directly to the `useChat` context actions (`sendMessage`, `editMessage`, `cancelStream`, `regenerate`). It keeps UI-only states (e.g., input string, height adjustments) locally, which is correct.
- **Cleanliness**: Contains stub buttons for file attachment and microphone inputs (which are UI placeholders with no handlers, but act as visual stubs). Contains a caught `console.error` on clipboard copy failure.

### 2.5 `frontend/src/components/chat/ChatMessage.jsx` & Presentation Cards
- Includes `ChatMessage.jsx`, `ToolCallCard.jsx`, and `ChatEmptyState.jsx`.
- **Role**: View (Presentation Components).
- **Modularity**: Excellent. They receive data purely through React props and emit user actions via callbacks (`onSendMessage`, `onCardClick`). They have zero side effects or direct service coupling.

---

## 3. Detailed MVVM and SWR Strategy

### 3.1 Custom Hook for Resource Recommendations
To resolve the MVVM violation in `SidebarResources.jsx`, we propose creating a custom SWR hook `useRecommendedResources.js`. 
This hook will:
1. Handle SWR fetching of course resources, managing cache, load states, and error propagation.
2. Encapsulate the `activeKPs` extraction logic from `messages`.
3. Filter the resources based on extracted knowledge points and title mappings.
4. Expose clean, reactive outputs to `SidebarResources.jsx`.

### 3.2 SWR Integration in ChatContext
To align `ChatContext.jsx` with the SWR architectural directive:
1. **Sessions List**: Refactor the session retrieval from `chatService.getSessions` to use SWR. This enables cache-first retrieval, automatic revalidation, and optimistic updates on deletion.
2. **Messages & History**:
   - **Why keep messages in local state?** In a streaming chat system, messages receive real-time, high-frequency incremental updates (e.g., SSE chunks, intermediate tool call states, diagrams). Managing this directly in SWR cache via `mutate` would lead to complex race conditions. Furthermore, SWR background revalidations (e.g., on focus) could fetch old history and overwrite volatile, actively streaming messages.
   - **Recommendation**: Retain the local `messages` state in the context for streaming stability. Fetch the initial history via SWR or manual API call *only* when `activeSession` switches, keeping the stream updates isolated.

---

## 4. Proposed Edits & Patches

We have drafted the precise changes required.

### 4.1 Create New Custom Hook: `frontend/src/hooks/useRecommendedResources.js`
This file implements the resource recommendations ViewModel using SWR.

```javascript
import useSWR from 'swr';
import { useMemo } from 'react';
import { learningService } from '../api/services/learning';

const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200) {
    throw new Error(res.message || '请求失败');
  }
  return res.data;
};

/**
 * Custom hook to fetch and recommend course resources based on chat history active knowledge points.
 * Implements MVVM pattern by separating data fetching, filtering logic, and state management.
 */
export function useRecommendedResources(activeCourseId, messages) {
  // Fetch course resources using SWR
  const { data: resourcesRes, error, isLoading, mutate } = useSWR(
    activeCourseId ? ['courseResources', activeCourseId] : null,
    () => fetcherWrapper(learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 100 })),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const resources = useMemo(() => {
    if (!resourcesRes) return [];
    return Array.isArray(resourcesRes.resources || resourcesRes)
      ? (resourcesRes.resources || resourcesRes)
      : [];
  }, [resourcesRes]);

  // Extract active knowledge points from the latest assistant response
  const activeKPs = useMemo(() => {
    if (!messages || messages.length === 0) return [];
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.knowledge_points && msg.knowledge_points.length > 0) {
        return msg.knowledge_points;
      }
    }
    return [];
  }, [messages]);

  // Filter resources that match the active knowledge points
  const recommendedResources = useMemo(() => {
    return resources.filter(res => {
      if (activeKPs.length === 0) return true;
      return activeKPs.some(kp => 
        res.knowledge_point?.toLowerCase().includes(kp.toLowerCase()) ||
        res.title?.toLowerCase().includes(kp.toLowerCase())
      );
    });
  }, [resources, activeKPs]);

  return {
    recommendedResources,
    error: !!error,
    isLoading,
    mutate
  };
}
```

### 4.2 Refactor `SidebarResources.jsx`
Applying the custom hook transforms `SidebarResources.jsx` into a clean presentational View:

```jsx
import { useCourse } from '../../context/CourseContext';
import { useChat } from '../../context/ChatContext';
import { useRecommendedResources } from '../../hooks/useRecommendedResources';
import Icon from '../Icon';
import { Link } from 'react-router-dom';

export default function SidebarResources({ activeCourseName, rightCollapsed, rightDrawerOpen, onToggleCollapse, onCloseDrawer }) {
  const { activeCourseId } = useCourse();
  const { messages } = useChat();

  // Retrieve data from ViewModel Hook
  const { recommendedResources, error, isLoading } = useRecommendedResources(activeCourseId, messages);

  return (
    <>
      {rightDrawerOpen && (
        <div 
          onClick={onCloseDrawer}
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 xl:hidden transition-opacity duration-300"
        />
      )}
      <aside className={`
        bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0 overflow-hidden
        /* Mobile Drawer Style */
        fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-full
        ${rightDrawerOpen ? 'translate-x-0' : 'translate-x-full xl:translate-x-0'}
        /* Desktop Collapse Style */
        ${rightCollapsed ? 'xl:w-16 xl:border-l xl:border-slate-200' : 'xl:w-72 xl:border-l xl:border-slate-200'}
      `}>
        <div className="w-72 h-full flex flex-col">
          <div className="flex-1 flex flex-col w-72 h-full">
            <div className="p-5 border-b border-slate-100">
              <div className="text-[11px] font-bold text-slate-400 mb-1">当前学习上下文</div>
              <div className="text-slate-800 font-semibold text-sm truncate" title={activeCourseName}>
                {activeCourseName}
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
              <div className="flex justify-between items-center mb-4">
                <span className="text-[12px] font-bold text-slate-400">相关资源推荐</span>
                <span className="text-[12px] text-cyan-600 cursor-pointer hover:underline">全部</span>
              </div>
              
              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-10 text-slate-400">
                  <span className="inline-block w-6 h-6 rounded-full border-2 border-cyan-200 border-t-cyan-500 animate-spin mb-2"></span>
                  <span className="text-[12px]">加载中...</span>
                </div>
              ) : error ? (
                <div className="border border-red-200 border-dashed rounded-xl p-4 bg-red-50 flex flex-col items-center justify-center text-center mt-6">
                  <div className="w-12 h-12 bg-red-100 rounded-full mb-3 flex items-center justify-center text-red-500">
                    <Icon name="error_outline" className="material-symbols-outlined text-2xl"/>
                  </div>
                  <div className="text-[14px] font-semibold text-red-700 mb-1">加载失败</div>
                  <div className="text-[12px] text-red-600 leading-relaxed px-2 mt-2">
                    无法获取推荐资源，请稍后重试。
                  </div>
                </div>
              ) : recommendedResources.length > 0 ? (
                <div className="space-y-3">
                  {recommendedResources.map(res => {
                    let icon = 'description';
                    let iconBg = 'bg-blue-50 text-blue-600';
                    if (res.type === 'mindmap') {
                      icon = 'hub';
                      iconBg = 'bg-purple-50 text-purple-600';
                    } else if (res.type === 'reading') {
                      icon = 'menu_book';
                      iconBg = 'bg-amber-50 text-amber-600';
                    } else if (res.type === 'code') {
                      icon = 'code';
                      iconBg = 'bg-emerald-50 text-emerald-600';
                    } else if (res.type === 'video') {
                      icon = 'video_library';
                      iconBg = 'bg-rose-50 text-rose-600';
                    }
                    return (
                      <Link 
                        key={res.id} 
                        to={"/resource/" + res.id} 
                        className="flex gap-3 p-3 rounded-xl border border-slate-100 hover:border-cyan-200 hover:bg-cyan-50/30 transition-all duration-200 group cursor-pointer block"
                      >
                        <div className={`w-9 h-9 rounded-lg ${iconBg} flex items-center justify-center flex-shrink-0 font-medium`}>
                          <Icon name={icon} className="material-symbols-outlined text-[20px]"/>
                        </div>
                        <div className="min-w-0 flex-1">
                          <h4 className="text-[13px] font-semibold text-slate-800 group-hover:text-cyan-700 transition-colors line-clamp-1 mb-0.5">
                            {res.title}
                          </h4>
                          {res.description && (
                            <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                              {res.description}
                            </p>
                          )}
                          {res.knowledge_point && (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              <span className="inline-block px-1.5 py-0.5 text-[9px] font-medium bg-slate-100 text-slate-600 rounded">
                                {res.knowledge_point}
                              </span>
                            </div>
                          )}
                        </div>
                      </Link>
                    );
                  })}
                </div>
              ) : (
                <div className="border border-slate-200 border-dashed rounded-xl p-4 bg-slate-50 flex flex-col items-center justify-center text-center mt-6">
                  <div className="w-12 h-12 bg-slate-100 rounded-full mb-3 flex items-center justify-center text-slate-400">
                    <Icon name="inventory_2" className="material-symbols-outlined text-2xl"/>
                  </div>
                  <div className="text-[14px] font-semibold text-slate-700 mb-1">暂无推荐资源</div>
                  <div className="text-[12px] text-slate-500 leading-relaxed px-2 mt-2">
                    这里会根据您的学习进度，为您推荐合适的课程资源。
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Desktop Collapse Handle */}
        <button 
          onClick={onToggleCollapse}
          className="hidden xl:flex absolute left-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
          title={rightCollapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          <Icon name={rightCollapsed ? 'chevron_left' : 'chevron_right'} className="material-symbols-outlined text-[16px] select-none"/>
        </button>
      </aside>
    </>
  );
}
```

### 4.3 Refactor `ChatContext.jsx` to Use SWR for Sessions List
Here is the diff patch style representation of the refactoring proposal for `ChatContext.jsx`. This integrates SWR for `sessions` and hooks it into session selection and deletions.

```jsx
// 1. Add import
import useSWR from 'swr';

// 2. Modify State and Fetching inside ChatProvider:
export const ChatProvider = ({ children }) => {
  const { activeCourseId } = useCourse();
  
  // Use SWR to manage session list data fetching and caching
  const { data: sessionsRes, mutate: mutateSessions } = useSWR(
    activeCourseId ? ['chatSessions', activeCourseId] : null,
    async () => {
      const res = await chatService.getSessions(activeCourseId);
      if (res.code !== 200) throw new Error(res.message || '获取会话列表失败');
      return res.data.conversations || res.data || [];
    },
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false
    }
  );

  const sessions = sessionsRes || [];
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  
  const abortControllerRef = useRef(null);
  const lastMessageIdRef = useRef(null);

  // Sync activeSession when course changes or session list loads
  useEffect(() => {
    if (activeCourseId) {
      if (sessions.length > 0) {
        // Auto-select first session if current activeSession is invalid/unset
        if (!activeSession || !sessions.some(s => s.id === activeSession)) {
          setActiveSession(sessions[0].id);
        }
      } else {
        setActiveSession(null);
        setMessages([]);
      }
    } else {
      setActiveSession(null);
      setMessages([]);
    }
  }, [sessions, activeCourseId]);

  // Load chat history when activeSession changes
  useEffect(() => {
    if (activeSession) {
      chatService.getHistory(activeSession).then(res => {
        if (res.code === 200 && res.data) {
          setMessages(normalizeMessages(res.data.messages));
        }
      }).catch(console.error);
    } else {
      setMessages([]);
    }
  }, [activeSession]);

  // 3. Modify deleteSession to use SWR mutate (optimistic update)
  const deleteSession = async (sessionId) => {
    try {
      // Optimistic update of SWR cache
      if (mutateSessions) {
        mutateSessions(prev => prev ? prev.filter(s => s.id !== sessionId) : [], false);
      }
      await chatService.deleteSession(sessionId);
      
      if (activeSession === sessionId) {
        resetConversation();
        const remaining = sessions.filter(s => s.id !== sessionId);
        if (remaining.length > 0) {
          setActiveSession(remaining[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to delete session', err);
      // Revert cache on failure
      if (mutateSessions) mutateSessions();
    }
  };

  // 4. Modify onDone in stream handlers to trigger session list refresh:
  const createStreamHandlers = (targetId) => {
    return {
      // ... onMessage handlers ...
      onDone: (doneData) => {
        const finalMessageId = doneData.message_id || `ai-${crypto.randomUUID()}`;
        lastMessageIdRef.current = finalMessageId;
        setMessages(prev => updateTargetMessage(prev, targetId, m => ({
          ...m, id: targetId === 'ai-placeholder' ? finalMessageId : m.id, loading: false, toolCalls: completeRunningToolCalls(m.toolCalls)
        })));
        setIsSending(false);
        abortControllerRef.current = null;
        
        if (!activeSession && doneData.conversation_id) {
          setActiveSession(doneData.conversation_id);
          // Revalidate the SWR session cache to pull the new conversation
          if (mutateSessions) {
            mutateSessions();
          }
        }
      },
      onError: (err) => {
        // ...
      }
    };
  };

  // ... rest of the file ...
}
```
