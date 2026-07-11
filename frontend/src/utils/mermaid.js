// src/utils/mermaid.js
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  securityLevel: 'strict',
  theme: 'default',
  suppressErrors: true,
  errorCallback: () => {},
});

export const normalizeMermaidSource = (content) => {
  const trimmed = (content || '').trim();
  const fenced = trimmed.match(/^```(?:mermaid)?\s*([\s\S]*?)```$/i);
  return fenced ? fenced[1].trim() : trimmed;
};

export const sanitizeMermaidSource = (content) => {
  let source = normalizeMermaidSource(content);

  // Fix subgraph titles that might contain invalid characters like spaces or quotes,
  // preventing Mermaid parsing errors.
  source = source.replace(/^([ \t]*subgraph\s+)(.+)$/gm, (match, prefix, title) => {
    title = title.trim();
    if (/^[\w-]+\s*\[.*\]$/.test(title)) return match;
    if (title.startsWith('"') && title.endsWith('"')) return match;
    if (/^[A-Za-z0-9_\-\u4e00-\u9fa5]+$/.test(title)) return match;
    
    const escapedTitle = title.replace(/"/g, '\\"');
    return `${prefix}"${escapedTitle}"`;
  });

  // Define the opening patterns we want to match, ordered by specificity
  const patterns = [
    { open: '((', close: '))', openChar: '(', closeChar: ')' },
    { open: '{{', close: '}}', openChar: '{', closeChar: '}' },
    { open: '[/', close: '/]', openChar: '[', closeChar: ']' },
    { open: '[\\', close: '\\]', openChar: '[', closeChar: ']' },
    { open: '[', close: ']', openChar: '[', closeChar: ']' },
    { open: '(', close: ')', openChar: '(', closeChar: ')' },
    { open: '{', close: '}', openChar: '{', closeChar: '}' },
    { open: '>', close: ']', openChar: '[', closeChar: ']' }
  ];

  // Regexp to find a word boundary, an identifier, optional spaces, and one of the openings
  const escapedOpens = patterns.map(p => p.open.split('').map(c => '\\' + c).join('')).join('|');
  const regex = new RegExp(`\\b(\\w+)\\s*(${escapedOpens})`, 'g');

  let match;
  let lastIndex = 0;
  let result = '';

  while ((match = regex.exec(source)) !== null) {
    const id = match[1];
    const openStr = match[2];
    const matchStart = match.index;
    
    const config = patterns.find(p => p.open === openStr);
    if (!config) {
      result += source.substring(lastIndex, regex.lastIndex);
      lastIndex = regex.lastIndex;
      continue;
    }

    const { close: closeStr, openChar, closeChar } = config;
    
    // Scan forward from regex.lastIndex to find the matching closeStr
    let nesting = 1;
    let i = regex.lastIndex;
    let foundCloseIndex = -1;

    while (i < source.length) {
      if (source.substring(i, i + closeStr.length) === closeStr) {
        nesting--;
        if (nesting === 0) {
          foundCloseIndex = i;
          break;
        }
        i += closeStr.length;
        continue;
      }
      
      // If we see a nested open character
      if (source.charAt(i) === openChar) {
        nesting++;
      } else if (source.charAt(i) === closeChar) {
        nesting--;
        if (nesting === 0) {
          foundCloseIndex = i;
          break;
        }
      }
      i++;
    }

    if (foundCloseIndex !== -1) {
      const labelStart = regex.lastIndex;
      const labelEnd = foundCloseIndex;
      let label = source.substring(labelStart, labelEnd);

      const isQuoted = (label.startsWith('"') && label.endsWith('"')) || (label.startsWith("'") && label.endsWith("'"));
      if (!isQuoted) {
        const escapedLabel = label.replace(/"/g, '\\"');
        label = `"${escapedLabel}"`;
      }

      result += source.substring(lastIndex, matchStart);
      result += `${id}${openStr}${label}${closeStr}`;
      
      lastIndex = foundCloseIndex + closeStr.length;
      regex.lastIndex = lastIndex;
    } else {
      result += source.substring(lastIndex, regex.lastIndex);
      lastIndex = regex.lastIndex;
    }
  }

  result += source.substring(lastIndex);
  return result;
};

export default mermaid;
