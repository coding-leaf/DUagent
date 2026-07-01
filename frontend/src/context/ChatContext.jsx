// src/context/ChatContext.jsx
import { createContext, useContext, useState, useEffect, useRef, useMemo } from 'react';
import useSWR from 'swr';
import { chatService } from '../api/services/chat';
import { useCourse } from './CourseContext';
import { normalizeMessages } from '../utils/chatContent';
import { fetcherWrapper } from '../utils/fetcher';
import { MOCK_TOOL_DEMOS } from '../components/chat/mockToolDemos';

const ChatContext = createContext(null);

// Pure Helper Functions
const updateTargetMessage = (messages, targetId, updater) => {
  return messages.map(m => m.id === targetId ? updater(m) : m);
};

const completeRunningToolCalls = (toolCalls = []) => {
  return toolCalls.map(tc => tc.status === 'running' ? { ...tc, status: 'completed' } : tc);
};

const upsertToolCall = (toolCalls = [], update) => {
  const id = update.id;
  const existing = toolCalls.find(tc => tc.id === id);
  if (!existing) return [...toolCalls, update];
  return toolCalls.map(tc => tc.id === id ? { ...tc, ...update } : tc);
};

const normalizeArtifact = (event) => {
  const artifact = event.payload?.artifact;
  if (!artifact || !artifact.type) return null;
  return {
    id: artifact.id || `artifact-${crypto.randomUUID()}`,
    type: artifact.type,
    props: artifact.props || {},
    timestamp: event.timestamp || new Date().toISOString()
  };
};

const completionMessageId = (event) => event.message_id || event.payload?.message_id || `ai-${crypto.randomUUID()}`;

const createEmptyAiMessage = (id = 'ai-placeholder') => ({
  id, role: 'assistant', content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [], toolCalls: []
});

export const ChatProvider = ({ children }) => {
  const { activeCourseId } = useCourse();
  const { data: sessionsRes, mutate: mutateSessions } = useSWR(
    activeCourseId ? ['chatSessions', activeCourseId] : null,
    () => fetcherWrapper(chatService.getSessions(activeCourseId))
  );

  const sessions = useMemo(() => {
    return sessionsRes?.data?.conversations || sessionsRes?.data || [];
  }, [sessionsRes]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [workspaceArtifacts, setWorkspaceArtifacts] = useState([]);

  const sendMockArtifact = (payload) => {
    const newArtifact = {
      id: `artifact-${crypto.randomUUID()}`,
      type: payload.type,
      props: payload.props || {},
      timestamp: new Date().toISOString()
    };
    setWorkspaceArtifacts(prev => [...prev, newArtifact]);
  };

  const runMockToolDemo = (demoKey) => {
    const demo = MOCK_TOOL_DEMOS[demoKey];
    if (!demo || isSending) return;

    const createdArtifacts = demo.artifacts.map((artifact) => ({
      id: `artifact-${crypto.randomUUID()}`,
      type: artifact.type,
      props: artifact.props || {},
      timestamp: new Date().toISOString()
    }));

    setMessages(prev => [
      ...prev,
      { id: `user-${crypto.randomUUID()}`, role: 'user', content: demo.prompt },
      {
        id: `ai-${crypto.randomUUID()}`,
        role: 'assistant',
        content: demo.answer,
        loading: false,
        diagrams: [],
        knowledge_points: [],
        suggestions: ['继续细化这份内容', '把结果保存为个性化资源'],
        toolCalls: demo.toolCalls
      }
    ]);
    setWorkspaceArtifacts(prev => [...prev, ...createdArtifacts]);
  };
  
  const abortControllerRef = useRef(null);
  const lastMessageIdRef = useRef(null);
  const prevCourseIdRef = useRef(activeCourseId);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (prevCourseIdRef.current !== activeCourseId) {
      prevCourseIdRef.current = activeCourseId;
      setActiveSession(null);
      setMessages([]);
      setWorkspaceArtifacts([]);
      return;
    }

    if (activeCourseId && sessions.length > 0) {
      const activeSessionExists = sessions.some(s => s.id === activeSession);
      if (!activeSession || !activeSessionExists) {
        setActiveSession(sessions[0].id);
      }
    } else if (activeCourseId && sessionsRes) {
      setActiveSession(null);
      setMessages([]);
      setWorkspaceArtifacts([]);
    }
  }, [sessions, activeCourseId, activeSession, sessionsRes]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (activeSession) {
      chatService.getHistory(activeSession).then(res => {
        if (res.code === 200 && res.data) {
          setMessages(normalizeMessages(res.data.messages));
          setWorkspaceArtifacts([]);
        }
      }).catch(console.error);
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages([]);
      setWorkspaceArtifacts([]);
    }
  }, [activeSession]);

  const cancelStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
  };

  useEffect(() => {
    // This cleanup runs only when ChatProvider unmounts (e.g. app exit/logout).
    // In React Strict Mode, this will execute on initial mount due to double-mount,
    // but the null check in cancelStream prevents issues.
    return () => cancelStream();
  }, []);

  const resetConversation = () => {
    cancelStream();
    setActiveSession(null);
    lastMessageIdRef.current = null;
    setMessages([]);
    setWorkspaceArtifacts([]);
    setIsSending(false);
  };

  const deleteSession = async (sessionId) => {
    try {
      const updatedSessions = sessions.filter(s => s.id !== sessionId);
      const newCacheData = sessionsRes ? {
        ...sessionsRes,
        data: sessionsRes.data && Array.isArray(sessionsRes.data)
          ? updatedSessions
          : { ...sessionsRes.data, conversations: updatedSessions }
      } : undefined;

      mutateSessions(newCacheData, { revalidate: false });

      await chatService.deleteSession(sessionId);
      mutateSessions();

      if (activeSession === sessionId) {
        resetConversation();
        if (updatedSessions.length > 0) {
          setActiveSession(updatedSessions[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to delete session', err);
      mutateSessions();
    }
  };

  const createStreamHandlers = (targetId) => {
    const completeMessage = (event, failed = false) => {
      const finalMessageId = completionMessageId(event);
      lastMessageIdRef.current = finalMessageId;
      setMessages(prev => updateTargetMessage(prev, targetId, m => ({
        ...m,
        id: targetId === 'ai-placeholder' ? finalMessageId : m.id,
        content: failed
          ? `${m.content || ''}\n\n[生成失败: ${event.payload?.message || event.payload?.reason || 'agent_failed'}]`
          : m.content,
        loading: false,
        isError: failed || m.isError,
        toolCalls: completeRunningToolCalls(m.toolCalls)
      })));
      setIsSending(false);
      abortControllerRef.current = null;

      if (!activeSession && event.conversation_id) {
        setActiveSession(event.conversation_id);
        mutateSessions();
      }
    };

    return {
      onMessage: (event) => {
        if (event.type === 'artifact_created') {
          const artifact = normalizeArtifact(event);
          if (artifact) setWorkspaceArtifacts(prev => [...prev, artifact]);
        }

        if (event.type === 'workflow_completed') {
          completeMessage(event, false);
          return;
        }

        if (event.type === 'workflow_failed') {
          completeMessage(event, true);
          return;
        }

        setMessages(prev => updateTargetMessage(prev, targetId, m => {
          switch (event.type) {
            case 'workflow_started':
              return { ...m, runId: event.run_id || m.runId };
            case 'text_delta':
              return { ...m, content: m.content + (event.payload?.delta || '') };
            case 'tool_started':
              return {
                ...m,
                toolCalls: upsertToolCall(m.toolCalls, {
                  id: event.payload?.tool_call_id || `tool-${crypto.randomUUID()}`,
                  name: event.payload?.tool_name || '工具调用',
                  status: 'running'
                })
              };
            case 'tool_completed':
              return {
                ...m,
                toolCalls: upsertToolCall(m.toolCalls, {
                  id: event.payload?.tool_call_id || 'unknown',
                  status: event.payload?.state === 'error' ? 'error' : 'completed',
                  outputSummary: event.payload?.summary
                })
              };
            case 'tool_failed':
              return {
                ...m,
                toolCalls: upsertToolCall(m.toolCalls, {
                  id: event.payload?.tool_call_id || 'unknown',
                  name: event.payload?.tool_name || '工具调用',
                  status: 'error',
                  outputSummary: event.payload?.reason || event.payload?.message
                })
              };
            case 'source_refs':
              return {
                ...m,
                sourceRefs: event.payload?.sources || []
              };
            case 'critic_completed':
              return {
                ...m,
                reviewFlagged: event.payload?.passed === false,
                reviewReason: event.payload?.reason || m.reviewReason
              };
            default:
              return m;
          }
        }));
      },
      onError: (err) => {
        console.error('Chat stream error:', err);
        completeMessage(
          {
            type: 'workflow_failed',
            payload: { message: err.message || '网络连接故障' }
          },
          true
        );
      }
    };
  };

  const startStream = (targetId, requestPayload) => {
    setIsSending(true);
    cancelStream();
    const handlers = createStreamHandlers(targetId);
    abortControllerRef.current = chatService.streamChat(
      { ...requestPayload, scope: 'course', course_id: activeCourseId, conversation_id: activeSession },
      handlers.onMessage,
      handlers.onError
    );
  };

  const sendMessage = (textToSend) => {
    if (!textToSend || isSending || !activeCourseId) return;
    lastMessageIdRef.current = null;

    setMessages(prev => [
      ...prev,
      { id: `user-${crypto.randomUUID()}`, role: 'user', content: textToSend },
      createEmptyAiMessage()
    ]);
    
    startStream('ai-placeholder', { message: textToSend, action: 'chat' });
  };

  const regenerate = () => {
    if (isSending) return;
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    const lastAiIdx = messages.map(m => m.role).lastIndexOf('assistant');
    if (!lastUserMsg || lastAiIdx < 0) return;

    const targetId = messages[lastAiIdx].id;
    setMessages(prev => prev.map((m, i) => i === lastAiIdx ? { ...createEmptyAiMessage(m.id), toolCalls: [{ id: 'regenerating', name: '正在重新生成...', status: 'running' }] } : m));
    
    startStream(targetId, { message: lastUserMsg.content, action: 'regenerate' });
  };

  const editMessage = (newContent) => {
    if (!newContent.trim() || isSending) return;
    const lastUserIdx = messages.map(m => m.role).lastIndexOf('user');
    const lastAiIdx = messages.map(m => m.role).lastIndexOf('assistant');
    if (lastUserIdx < 0) return;

    const targetId = lastAiIdx >= 0 ? messages[lastAiIdx].id : 'ai-placeholder';
    setMessages(prev => prev.map((m, i) => {
      if (i === lastUserIdx) return { ...m, content: newContent };
      if (i === lastAiIdx) return { ...createEmptyAiMessage(m.id), toolCalls: [{ id: 'regenerating', name: '正在重新生成...', status: 'running' }] };
      return m;
    }));
    
    startStream(targetId, { message: newContent, action: 'edit' });
  };

  return (
    <ChatContext.Provider value={{
      sessions, activeSession, setActiveSession, messages, isSending,
      sendMessage, regenerate, editMessage, cancelStream, resetConversation, deleteSession,
      workspaceArtifacts, sendMockArtifact, runMockToolDemo
    }}>
      {children}
    </ChatContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useChat = () => useContext(ChatContext);
