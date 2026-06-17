function fixSubgraph(source) {
  return source.replace(/^([ \t]*subgraph\s+)(.+)$/gm, (match, prefix, title) => {
    title = title.trim();
    if (/^[\w-]+\s+\[.*\]$/.test(title)) return match;
    if (title.startsWith('"') && title.endsWith('"')) return match;
    if (/^[A-Za-z0-9_\-\u4e00-\u9fa5]+$/.test(title)) return match;
    
    const escapedTitle = title.replace(/"/g, '\\"');
    return `${prefix}"${escapedTitle}"`;
  });
}

const tests = [
  'subgraph 数组 int arr["5"] 的内存布局',
  '  subgraph id-1 [My Title]',
  'subgraph sub-graph',
];

tests.forEach(t => console.log(fixSubgraph(t)));
