/**
 * Parses the raw evaluation summary text into structured sections.
 * Expected sections: 学习范围、当前掌握、学习行为、下一步建议.
 */
export function parseSummaryText(text) {
  if (!text) return null;

  const markers = [
    { key: 'scope', marker: '学习范围：' },
    { key: 'mastery', marker: '当前掌握：' },
    { key: 'behavior', marker: '学习行为：' },
    { key: 'suggestions', marker: '下一步建议：' }
  ];

  const found = markers
    .map(m => ({ ...m, index: text.indexOf(m.marker) }))
    .filter(m => m.index !== -1)
    .sort((a, b) => a.index - b.index);

  if (found.length === 0) {
    return { scope: text, mastery: '', behavior: '', suggestions: [], suggestionsPrefix: '' };
  }

  const result = {
    scope: '',
    mastery: '',
    behavior: '',
    suggestions: [],
    suggestionsPrefix: ''
  };

  for (let i = 0; i < found.length; i++) {
    const current = found[i];
    const next = found[i + 1];
    const startPos = current.index + current.marker.length;
    const endPos = next ? next.index : text.length;
    const content = text.substring(startPos, endPos).trim();

    if (current.key === 'suggestions') {
      const itemRegex = /(?:\d+[\)\）\、\.])\s*/g;
      const parts = content.split(itemRegex);
      
      const items = [];
      let prefix = '';
      if (parts[0] && parts[0].trim()) {
        prefix = parts[0].trim();
      }
      
      for (let j = 1; j < parts.length; j++) {
        const itemContent = parts[j].trim();
        if (itemContent) {
          let title = '';
          let desc = itemContent;
          
          // Check first for custom colons
          const colonIdx = itemContent.indexOf('：');
          const colonEnIdx = itemContent.indexOf(':');
          const finalColonIdx = colonIdx !== -1 ? colonIdx : colonEnIdx;
          
          if (finalColonIdx !== -1 && finalColonIdx < 20) {
            title = itemContent.substring(0, finalColonIdx).trim();
            desc = itemContent.substring(finalColonIdx + 1).trim();
          } else {
            // fallback split by comma or parentheses
            const splitIdx = itemContent.search(/[，（(,]/);
            if (splitIdx !== -1 && splitIdx < 20) {
              title = itemContent.substring(0, splitIdx).trim();
              desc = itemContent.substring(splitIdx).trim();
              if (desc.startsWith('，') || desc.startsWith(',') || desc.startsWith('；') || desc.startsWith(';')) {
                desc = desc.substring(1).trim();
              }
            } else {
              title = itemContent;
              desc = '';
            }
          }
          
          // Clean up trailing punctuation (commas, semicolons) from title and description
          title = title.replace(/[；;，,\s]+$/, '').trim();
          desc = desc.replace(/[；;，,\s]+$/, '').trim();

          items.push({
            id: j,
            title,
            desc
          });
        }
      }
      
      if (items.length === 0) {
        items.push({
          id: 1,
          title: '推荐学习建议',
          desc: content
        });
      }
      
      result.suggestions = items;
      result.suggestionsPrefix = prefix;
    } else {
      result[current.key] = content;
    }
  }

  return result;
}
