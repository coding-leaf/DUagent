function fixSubgraph(source) {
  return source.replace(/^([ \t]*subgraph\s+)(.+)$/gm, (match, prefix, title) => {
    title = title.trim();
    if (/^\w+\s+\[.*\]$/.test(title)) return match;
    if (title.startsWith('"') && title.endsWith('"')) return match;
    if (/^[A-Za-z0-9_\u4e00-\u9fa5]+$/.test(title)) return match;
    
    const escapedTitle = title.replace(/"/g, '\\"');
    return `${prefix}"${escapedTitle}"`;
  });
}

const tests = [
  'subgraph 数组 int arr["5"] 的内存布局',
  '  subgraph id1 [My Title]',
  'subgraph "Quoted Title"',
  'subgraph SimpleID',
  'subgraph 测试',
  'subgraph 测试 with space',
  'subgraph id1 ["With quotes"]'
];

tests.forEach(t => console.log(fixSubgraph(t)));
