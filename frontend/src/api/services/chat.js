import client from '../client';

const useMock = import.meta.env.VITE_USE_MOCK === 'true';
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const chatService = {
  // 获取会话列表
  getSessions: (courseId) => {
    return client.get('/tutoring/conversations', {
      params: {
        scope: 'course',
        course_id: courseId
      }
    });
  },

  // 获取特定会话的历史记录
  getHistory: (sessionId) => {
    return client.get(`/tutoring/conversations/${sessionId}`);
  },

  deleteSession: (sessionId) => {
    return client.delete(`/tutoring/conversations/${sessionId}`);
  },

  // 发送流式消息
  streamChat: (params, onMessage, onDone, onError) => {
    const { message, action = 'chat', scope = 'course', course_id, conversation_id } = params;

    if (useMock) {
      // Simulate stream response for mockup mode
      let count = 0;
      const dummyId = 'm-' + Date.now();
      const mockText = `(Mock AI 答疑助手)\n关于您提到的“${message}”，这里是对应的模拟解析。\n在实际运行中，此内容会通过 Server-Sent Events (SSE) 逐字流式传输。以下是二叉树的一个公式示例：\n\n$C = \\sum_{i=1}^{n} (i-1) = \\frac{n(n-1)}{2}$\n\n如果您想获取更详尽的解析，请尝试使用真实 API。`;
      const words = mockText.split(/(\s+)/);

      const interval = setInterval(() => {
        if (count < words.length) {
          const chunk = words[count];
          onMessage({
            type: 'chunk',
            content: chunk
          });
          count++;
        } else {
          clearInterval(interval);
          // Send diagram if user asked for it or as demo
          if (message.includes('图') || message.includes('AVL') || message.includes('树')) {
            onMessage({
              type: 'diagram',
              data: {
                type: 'mermaid',
                code: 'graph TD\n    A[20] --> B(10)\n    A --> C(30)'
              }
            });
          }
          onMessage({
            type: 'knowledge_points',
            points: ['二叉查找树', '平衡二叉树']
          });
          onDone({
            conversation_id: conversation_id || 'sess_mock_9527',
            message_id: dummyId
          });
        }
      }, 50);

      return () => clearInterval(interval);
    }

    // Real API stream using native fetch
    const url = `${apiBaseUrl}/tutoring/chat`;
    const token = localStorage.getItem('access_token');
    
    const controller = new AbortController();
    const { signal } = controller;

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify({
        message,
        action,
        scope,
        course_id,
        conversation_id: conversation_id || null
      }),
      signal,
    })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Save the last partial line back to the buffer
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data:')) continue;
          
          const dataStr = trimmed.slice(5).trim();
          if (!dataStr) continue;

          try {
            const parsed = JSON.parse(dataStr);
            if (parsed.type === 'chunk') {
              onMessage(parsed);
            } else if (parsed.type === 'diagram') {
              onMessage(parsed);
            } else if (parsed.type === 'knowledge_points') {
              onMessage(parsed);
            } else if (parsed.type === 'done') {
              onDone(parsed);
            } else if (parsed.type === 'review') {
              onMessage(parsed);
            } else {
              // Generic fallback
              onMessage(parsed);
            }
          } catch (e) {
            console.error('Failed to parse SSE line JSON:', dataStr, e);
          }
        }
      }
    })
    .catch((err) => {
      if (err.name === 'AbortError') {
        console.log('Fetch aborted');
      } else {
        onError(err);
      }
    });

    return () => controller.abort();
  }
};
