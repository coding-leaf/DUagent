import client from '../client';

export const chatService = {
  // 获取会话列表
  getSessions: () => {
    return client.get('/api/v1/chat/sessions');
  },

  // 获取特定会话的历史记录
  getHistory: (sessionId) => {
    return client.get(`/api/v1/chat/history?session_id=${sessionId}`);
  },

  // 发送消息 (Mock中为非流式返回)
  sendMessage: (sessionId, message) => {
    return client.post('/api/v1/chat/completions', {
      session_id: sessionId,
      message: message
    });
  }
};
