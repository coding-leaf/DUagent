import { reduceAssistantMessageForEvent } from './chatStreamEvents';

// 聊天正文展示工具：把模型可能产出的结构化输出（纯 JSON / 散文 + ```json 围栏 / 对象）
// 归一化为面向学生的纯文本，避免 JSON 块泄露到正文。
// 提取用括号配平而非非贪婪正则，因此 model_text 内嵌的 ```c 代码块/花括号不会截断解析。

function scanBalancedObjectEnd(text, start) {
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === '\\') esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return i;
    }
  }
  return -1;
}

// 扫描文本，返回首个"能解析且含 model_text/content"的 JSON object；找不到返回 null。
function extractEnvelope(text) {
  let i = 0;
  while (i < text.length) {
    const start = text.indexOf('{', i);
    if (start === -1) return null;
    const end = scanBalancedObjectEnd(text, start);
    if (end === -1) {
      i = start + 1;
      continue;
    }
    try {
      const obj = JSON.parse(text.slice(start, end + 1));
      if (obj && typeof obj === 'object' && (obj.model_text || obj.content)) {
        return obj;
      }
    } catch {
      // 此处不是合法 JSON，继续向后扫描
    }
    i = end + 1;
  }
  return null;
}

export function extractModelText(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (typeof value === 'object') {
    return value.model_text
      || value.code
      || value.name
      || value.title
      || value.knowledge_point
      || value.label
      || value.content
      || value.id
      || JSON.stringify(value);
  }
  if (typeof value !== 'string') return String(value);

  const str = value;

  // 1. 整串就是 JSON object
  const trimmed = str.trim();
  if (trimmed.startsWith('{')) {
    try {
      const obj = JSON.parse(trimmed);
      if (obj && typeof obj === 'object' && (obj.model_text || obj.content)) {
        return obj.model_text || obj.content;
      }
    } catch {
      // 非完整 JSON（如流式中途），继续走下面的逻辑
    }
  }

  // 2. 散文 + ```json 围栏：括号配平提取后取 model_text（正确跳过嵌套 ```c）
  const envelope = extractEnvelope(str);
  if (envelope) {
    return envelope.model_text || envelope.content;
  }

  // 3. 普通文本
  return str;
}

export const normalizeTextList = (value) => {
  const list = Array.isArray(value) ? value : [value];
  return list.map(extractModelText).map(item => item?.trim()).filter(Boolean);
};

const restoreToolCalls = (message) => {
  if (Array.isArray(message?.toolCalls) && message.toolCalls.length > 0) {
    return message.toolCalls;
  }
  const events = message?.meta?.tool_events;
  if (!Array.isArray(events)) return [];
  const restored = events.reduce(
    reduceAssistantMessageForEvent,
    { content: '', toolCalls: [], parts: [] }
  );
  return restored.toolCalls;
};

export const normalizeMessage = (message, index = 0) => {
  const normalizedId = message?.id || message?.message_id || `${message?.role || 'message'}-${message?.timestamp || index}`;
  let contentObj = message?.content;
  if (typeof contentObj === 'string' && contentObj.trim().startsWith('{')) {
    try { contentObj = JSON.parse(contentObj); } catch { /* ignore */ }
  }
  let displayContent;
  let diagrams = message?.diagrams || [];
  let knowledge_points = message?.knowledge_points || [];
  let suggestions = message?.suggestions || [];

  if (typeof contentObj === 'object' && contentObj !== null) {
    displayContent = contentObj.model_text || contentObj.content || JSON.stringify(contentObj);
    if (contentObj.diagram && !diagrams.length) diagrams = [contentObj.diagram];
    if (contentObj.diagrams && !diagrams.length) diagrams = contentObj.diagrams;
    if (contentObj.knowledge_points && !knowledge_points.length) knowledge_points = contentObj.knowledge_points;
    if (contentObj.suggestion && !suggestions.length) suggestions = [contentObj.suggestion];
    if (contentObj.suggestions && !suggestions.length) suggestions = contentObj.suggestions;
  } else {
    displayContent = extractModelText(message?.content);
  }

  return {
    ...message,
    id: normalizedId,
    content: displayContent,
    diagrams: Array.isArray(diagrams) ? diagrams : (diagrams ? [diagrams] : []),
    knowledge_points: normalizeTextList(knowledge_points),
    suggestions: normalizeTextList(suggestions),
    toolCalls: restoreToolCalls(message),
  };
};

export const normalizeMessages = (items) => (Array.isArray(items) ? items.map(normalizeMessage) : []);
