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
