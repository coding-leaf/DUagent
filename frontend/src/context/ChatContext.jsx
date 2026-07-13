// src/context/ChatContext.jsx
import { createContext, useContext, useState, useEffect, useRef, useMemo } from 'react';
import useSWR from 'swr';
import { chatService } from '../api/services/chat';
import { useCourse } from './CourseContext';
import { normalizeMessages } from '../utils/chatContent';
import { fetcherWrapper } from '../utils/fetcher';
import { useRunLogs } from '../hooks/useRunLogs';
import {
  completeRunningToolCalls,
  completeRunningParts,
  completionMessageId,
  createEmptyAiMessage,
  normalizeArtifact,
  reduceAssistantMessageForEvent,
  updateTargetMessage
} from '../utils/chatStreamEvents';

const ChatContext = createContext(null);
const PLAN_MODE_PREFIX = '请先制定一个简短执行计划，再根据计划调用必要工具完成请求。计划应简洁，并在执行过程中及时更新任务状态。\n\n用户请求：\n';

const buildAgentMessage = (message, options = {}) => {
  return options.planMode ? `${PLAN_MODE_PREFIX}${message}` : message;
};

const artifactsFromMessages = (messages = []) => {
  const artifactsMap = new Map();
  messages.forEach(message => {
    const artifacts = message?.meta?.artifacts;
    if (Array.isArray(artifacts)) {
      artifacts
        .filter(artifact => artifact && artifact.type)
        .forEach(artifact => {
          const id = artifact.id || `artifact-${crypto.randomUUID()}`;
          artifactsMap.set(id, {
            id,
            type: artifact.type,
            title: artifact.title || null,
            props: artifact.props || {},
            timestamp: artifact.timestamp || message.timestamp || new Date().toISOString()
          });
        });
    }
  });
  return Array.from(artifactsMap.values());
};

export const ChatProvider = ({ children }) => {
  const { activeCourseId } = useCourse();
  const { data: sessionsRes, mutate: mutateSessions } = useSWR(
    activeCourseId ? ['chatSessions', activeCourseId] : null,
    () => fetcherWrapper(chatService.getSessions(activeCourseId))
  );

  const sessions = useMemo(() => {
    return sessionsRes?.data?.conversations || sessionsRes?.data || [];
  }, [sessionsRes]);
  const [activeSession, setActiveSessionState] = useState(null);
  const [isDraftConversation, setIsDraftConversation] = useState(false);
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [workspaceArtifacts, setWorkspaceArtifacts] = useState([]);
  const [activeArtifactId, setActiveArtifactId] = useState(null);
  const [hiddenArtifactIds, setHiddenArtifactIds] = useState([]);
  const { runLogs, appendRunLog, clearRunLogs } = useRunLogs();

  const hideArtifact = (id) => {
    setHiddenArtifactIds(prev => {
      const next = [...prev, id];
      if (activeArtifactId === id) {
        const visible = workspaceArtifacts.filter(a => !next.includes(a.id));
        setActiveArtifactId(visible.length > 0 ? visible[visible.length - 1].id : null);
      }
      return next;
    });
  };

  const restoreArtifact = (id) => {
    setHiddenArtifactIds(prev => prev.filter(i => i !== id));
    setActiveArtifactId(id);
  };

  const abortControllerRef = useRef(null);
  const lastMessageIdRef = useRef(null);
  const prevCourseIdRef = useRef(activeCourseId);
  const pendingSessionIdRef = useRef(null);

  const setActiveSession = (sessionId) => {
    pendingSessionIdRef.current = null;
    setIsDraftConversation(false);
    setActiveSessionState(sessionId);
    if (activeCourseId && sessionId) {
      localStorage.setItem(`active_session_id_${activeCourseId}`, sessionId);
    }
  };

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (prevCourseIdRef.current !== activeCourseId) {
      prevCourseIdRef.current = activeCourseId;
      pendingSessionIdRef.current = null;
      setActiveSessionState(null);
      setIsDraftConversation(false);
      setMessages([]);
      setWorkspaceArtifacts([]);
      setActiveArtifactId(null);
      setHiddenArtifactIds([]);
      clearRunLogs();
      return;
    }

    if (activeCourseId && sessions.length > 0) {
      const savedSessionId = localStorage.getItem(`active_session_id_${activeCourseId}`);
      const savedSessionExists = savedSessionId && sessions.some(s => s.id === savedSessionId);
      const activeSessionExists = sessions.some(s => s.id === activeSession);
      const pendingSessionId = pendingSessionIdRef.current;
      if (pendingSessionId && activeSession === pendingSessionId) {
        if (activeSessionExists) pendingSessionIdRef.current = null;
        else return;
      }
      if (!isDraftConversation && (!activeSession || !activeSessionExists)) {
        const nextSessionId = savedSessionExists ? savedSessionId : sessions[0].id;
        setActiveSessionState(nextSessionId);
        localStorage.setItem(`active_session_id_${activeCourseId}`, nextSessionId);
      }
    } else if (
      activeCourseId
      && sessionsRes
      && pendingSessionIdRef.current !== activeSession
    ) {
      setActiveSessionState(null);
      setIsDraftConversation(false);
      setMessages([]);
      setWorkspaceArtifacts([]);
      setActiveArtifactId(null);
      setHiddenArtifactIds([]);
      clearRunLogs();
      localStorage.removeItem(`active_session_id_${activeCourseId}`);
    }
  }, [sessions, activeCourseId, activeSession, sessionsRes, isDraftConversation, clearRunLogs]);
  /* eslint-enable react-hooks/set-state-in-effect */

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    let cancelled = false;
    setHiddenArtifactIds([]);
    if (activeSession) {
      chatService.getHistory(activeSession).then(res => {
        if (!cancelled && res.code === 200 && res.data) {
          const historyMessages = normalizeMessages(res.data.messages);
          setMessages(historyMessages);
          const artifacts = artifactsFromMessages(historyMessages);
          setWorkspaceArtifacts(artifacts);
          setActiveArtifactId(artifacts.length > 0 ? artifacts[artifacts.length - 1].id : null);
        }
      }).catch(console.error);
    } else {
      setMessages([]);
      setWorkspaceArtifacts([]);
      setActiveArtifactId(null);
    }
    return () => {
      cancelled = true;
    };
  }, [activeSession]);
  /* eslint-enable react-hooks/set-state-in-effect */

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
    pendingSessionIdRef.current = null;
    setActiveSessionState(null);
    setIsDraftConversation(true);
    if (activeCourseId) {
      localStorage.removeItem(`active_session_id_${activeCourseId}`);
    }
    lastMessageIdRef.current = null;
    setMessages([]);
    setWorkspaceArtifacts([]);
    setActiveArtifactId(null);
    clearRunLogs();
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
          setActiveSessionState(updatedSessions[0].id);
          setIsDraftConversation(false);
          if (activeCourseId) {
            localStorage.setItem(`active_session_id_${activeCourseId}`, updatedSessions[0].id);
          }
        } else if (activeCourseId) {
          localStorage.removeItem(`active_session_id_${activeCourseId}`);
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
      const failureMessage = `[生成失败: ${event.payload?.message || event.payload?.reason || 'agent_failed'}]`;
      lastMessageIdRef.current = finalMessageId;
      setMessages(prev => updateTargetMessage(prev, targetId, m => ({
        ...m,
        id: targetId === 'ai-placeholder' ? finalMessageId : m.id,
        content: failed
          ? `${m.content || ''}\n\n${failureMessage}`
          : m.content,
        loading: false,
        isError: failed || m.isError,
        toolCalls: completeRunningToolCalls(m.toolCalls),
        parts: failed
          ? [
              ...completeRunningParts(m.parts),
              { type: 'text', content: `\n\n${failureMessage}` }
            ]
          : completeRunningParts(m.parts)
      })));
      setIsSending(false);
      abortControllerRef.current = null;

      if (!activeSession && event.conversation_id) {
        pendingSessionIdRef.current = event.conversation_id;
        setIsDraftConversation(false);
        setActiveSessionState(event.conversation_id);
        if (activeCourseId) {
          localStorage.setItem(`active_session_id_${activeCourseId}`, event.conversation_id);
        }
        mutateSessions();
      }
    };

    return {
      onMessage: (event) => {
        appendRunLog(event);

        if (event.type === 'artifact_created') {
          const artifact = normalizeArtifact(event);
          if (artifact) {
            setWorkspaceArtifacts(prev => {
              const next = [...prev];
              const idx = next.findIndex(a => a.id === artifact.id);
              if (idx >= 0) {
                next[idx] = artifact;
              } else {
                next.push(artifact);
              }
              return next;
            });
            setHiddenArtifactIds(prev => prev.filter(i => i !== artifact.id));
            setActiveArtifactId(artifact.id);
          }
        }

        if (event.type === 'workflow_completed') {
          completeMessage(event, false);
          return;
        }

        if (event.type === 'workflow_failed') {
          completeMessage(event, true);
          return;
        }

        setMessages(prev => updateTargetMessage(
          prev,
          targetId,
          message => reduceAssistantMessageForEvent(message, event)
        ));
      },
      onError: (err) => {
        console.error('Chat stream error:', err);
        appendRunLog({
          type: 'workflow_failed',
          payload: {
            level: 'error',
            source: 'frontend.chat_stream',
            message: err.message || '网络连接故障'
          }
        });
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
    clearRunLogs();
    cancelStream();
    const handlers = createStreamHandlers(targetId);
    abortControllerRef.current = chatService.streamChat(
      { ...requestPayload, scope: 'course', course_id: activeCourseId, conversation_id: activeSession },
      handlers.onMessage,
      handlers.onError
    );
  };

  const sendMessage = (textToSend, options = {}) => {
    if (!textToSend || isSending || !activeCourseId) return;
    lastMessageIdRef.current = null;

    setMessages(prev => [
      ...prev,
      { id: `user-${crypto.randomUUID()}`, role: 'user', content: textToSend },
      createEmptyAiMessage()
    ]);
    
    startStream('ai-placeholder', { message: buildAgentMessage(textToSend, options), action: 'chat' });
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
      workspaceArtifacts, activeArtifactId, setActiveArtifactId, runLogs, clearRunLogs,
      hiddenArtifactIds, hideArtifact, restoreArtifact
    }}>
      {children}
    </ChatContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useChat = () => useContext(ChatContext);
