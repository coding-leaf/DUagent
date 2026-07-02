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
  return messages.flatMap(message => {
    const artifacts = message?.meta?.artifacts;
    if (!Array.isArray(artifacts)) return [];
    return artifacts
      .filter(artifact => artifact && artifact.type)
      .map(artifact => ({
        id: artifact.id || `artifact-${crypto.randomUUID()}`,
        type: artifact.type,
        props: artifact.props || {},
        timestamp: artifact.timestamp || message.timestamp || new Date().toISOString()
      }));
  });
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
  const { runLogs, appendRunLog, clearRunLogs } = useRunLogs();

  const abortControllerRef = useRef(null);
  const lastMessageIdRef = useRef(null);
  const prevCourseIdRef = useRef(activeCourseId);

  const setActiveSession = (sessionId) => {
    setIsDraftConversation(false);
    setActiveSessionState(sessionId);
  };

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (prevCourseIdRef.current !== activeCourseId) {
      prevCourseIdRef.current = activeCourseId;
      setActiveSessionState(null);
      setIsDraftConversation(false);
      setMessages([]);
      setWorkspaceArtifacts([]);
      setActiveArtifactId(null);
      clearRunLogs();
      return;
    }

    if (activeCourseId && sessions.length > 0) {
      const activeSessionExists = sessions.some(s => s.id === activeSession);
      if (!isDraftConversation && (!activeSession || !activeSessionExists)) {
        setActiveSessionState(sessions[0].id);
      }
    } else if (activeCourseId && sessionsRes) {
      setActiveSessionState(null);
      setIsDraftConversation(false);
      setMessages([]);
      setWorkspaceArtifacts([]);
      setActiveArtifactId(null);
      clearRunLogs();
    }
  }, [sessions, activeCourseId, activeSession, sessionsRes, isDraftConversation, clearRunLogs]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    if (activeSession) {
      chatService.getHistory(activeSession).then(res => {
        if (res.code === 200 && res.data) {
          const historyMessages = normalizeMessages(res.data.messages);
          setMessages(historyMessages);
          const artifacts = artifactsFromMessages(historyMessages);
          setWorkspaceArtifacts(artifacts);
          setActiveArtifactId(artifacts.length > 0 ? artifacts[artifacts.length - 1].id : null);
        }
      }).catch(console.error);
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages([]);
      setWorkspaceArtifacts([]);
      setActiveArtifactId(null);
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
    setActiveSessionState(null);
    setIsDraftConversation(true);
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
        toolCalls: completeRunningToolCalls(m.toolCalls),
        parts: completeRunningParts(m.parts)
      })));
      setIsSending(false);
      abortControllerRef.current = null;

      if (!activeSession && event.conversation_id) {
        setIsDraftConversation(false);
        setActiveSessionState(event.conversation_id);
        mutateSessions();
      }
    };

    return {
      onMessage: (event) => {
        appendRunLog(event);

        if (event.type === 'artifact_created') {
          const artifact = normalizeArtifact(event);
          if (artifact) {
            setWorkspaceArtifacts(prev => [...prev, artifact]);
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
      workspaceArtifacts, activeArtifactId, setActiveArtifactId, runLogs, clearRunLogs
    }}>
      {children}
    </ChatContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useChat = () => useContext(ChatContext);
