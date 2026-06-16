// src/context/ChatContext.jsx
import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { chatService } from '../api/services/chat';
import { useCourse } from './CourseContext';
import { normalizeTextList, normalizeMessages } from '../utils/chatContent';

const ChatContext = createContext(null);

// Pure Helper Functions
const updateTargetMessage = (messages, targetId, updater) => {
  return messages.map(m => m.id === targetId ? updater(m) : m);
};

const completeRunningToolCalls = (toolCalls = []) => {
  return toolCalls.map(tc => tc.status === 'running' ? { ...tc, status: 'completed' } : tc);
};

const createEmptyAiMessage = (id = 'ai-placeholder') => ({
  id, role: 'assistant', content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [], toolCalls: []
});

export const ChatProvider = ({ children }) => {
  const { activeCourseId } = useCourse();
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  
  const abortControllerRef = useRef(null);
  const lastMessageIdRef = useRef(null);

  useEffect(() => {
    if (activeCourseId) {
      chatService.getSessions(activeCourseId).then(res => {
        if (res.code === 200 && res.data) {
          const list = res.data.conversations || res.data;
          setSessions(list);
          if (list.length > 0) setActiveSession(list[0].id);
          else { setActiveSession(null); setMessages([]); }
        }
      }).catch(console.error);
    }
  }, [activeCourseId]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    return () => cancelStream();
  }, []);

  const resetConversation = () => {
    cancelStream();
    setActiveSession(null);
    lastMessageIdRef.current = null;
    setMessages([]);
    setIsSending(false);
  };

  const deleteSession = async (sessionId) => {
    try {
      await chatService.deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (activeSession === sessionId) {
        resetConversation();
        if (sessions.length > 1) {
          setActiveSession(sessions.find(s => s.id !== sessionId)?.id || null);
        }
      }
    } catch (err) {
      console.error('Failed to delete session', err);
    }
  };

  const createStreamHandlers = (targetId) => {
    return {
      onMessage: (msg) => {
        setMessages(prev => {
          if (msg.type === 'review') {
            const fallbackId = [...prev].reverse().find(m => m.role === 'assistant')?.id;
            const idToFlag = lastMessageIdRef.current || fallbackId;
            if (!idToFlag) return prev;
            return updateTargetMessage(prev, idToFlag, m => ({ ...m, reviewFlagged: true, reviewReason: msg.reason || 'off_topic' }));
          }

          return updateTargetMessage(prev, targetId, m => {
            switch (msg.type) {
              case 'status': {
                if (msg.stage === 'generation') {
                  const updatedToolCalls = (m.toolCalls || []).map(tc => tc.id === 'retrieval' ? { ...tc, status: 'completed' } : tc);
                  return { ...m, toolCalls: updatedToolCalls };
                } else if (msg.stage === 'retrieval') {
                  return { ...m, toolCalls: [{ id: 'retrieval', name: '检索课程知识库', status: 'running' }] };
                }
                return { ...m, toolCalls: [{ id: 'generic', name: msg.message || msg.content || '正在处理...', status: 'running' }] };
              }
              case 'chunk':
                return { ...m, content: m.content + (msg.content || ''), toolCalls: completeRunningToolCalls(m.toolCalls) };
              case 'diagram':
                return { ...m, diagrams: [...(m.diagrams || []), msg.data || msg.content] };
              case 'knowledge_points':
                return { ...m, knowledge_points: normalizeTextList(msg.knowledge_points || msg.points || msg.data || []) };
              case 'suggestion':
                return { ...m, suggestions: [...(m.suggestions || []), ...normalizeTextList(msg.data || msg.content || [])] };
              default:
                return m;
            }
          });
        });
      },
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
          chatService.getSessions(activeCourseId).then(res => {
            if (res.code === 200 && res.data) setSessions(res.data.conversations || res.data);
          });
        }
      },
      onError: (err) => {
        console.error('Chat stream error:', err);
        setMessages(prev => updateTargetMessage(prev, targetId, m => ({
          ...m, content: m.content + '\n\n[发送失败: ' + (err.message || '网络连接故障') + ']', loading: false, isError: true, toolCalls: completeRunningToolCalls(m.toolCalls)
        })));
        setIsSending(false);
        abortControllerRef.current = null;
      }
    };
  };

  const startStream = (targetId, requestPayload) => {
    setIsSending(true);
    cancelStream();
    const handlers = createStreamHandlers(targetId);
    abortControllerRef.current = chatService.streamChat(
      { ...requestPayload, scope: 'course', course_id: activeCourseId, conversation_id: activeSession },
      handlers.onMessage, handlers.onDone, handlers.onError
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
      sendMessage, regenerate, editMessage, cancelStream, resetConversation, deleteSession
    }}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => useContext(ChatContext);
