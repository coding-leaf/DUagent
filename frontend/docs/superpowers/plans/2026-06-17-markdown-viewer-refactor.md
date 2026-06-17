# MarkdownViewer 重构与修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽取全局可复用的 `MarkdownViewer` 组件，修复资源详情页的排版问题，同时为后续的全局重构打下基础，遵守“最小修改原则”。

**Architecture:** 
1. 抽取 `mermaid` 工具函数和初始化到 `src/utils/mermaid.js`。
2. 抽取 Markdown 和 Mermaid 渲染逻辑到 `src/components/common/MarkdownViewer.jsx`，支持动态 className 覆盖样式。
3. 改造 `ChatMessage.jsx`，清理冗余代码并引入新组件。
4. 修复 `ResourceDetail.jsx`，添加预处理层，移除 `prose` 等影响组件内样式的 className，并引入新组件。
5. 更新 `WORKFLOW.md`。

**Tech Stack:** React, react-markdown, mermaid, react-syntax-highlighter, TailwindCSS

---

### Task 1: 抽取 Mermaid 工具包 (`src/utils/mermaid.js`)

**Files:**
- Create: `src/utils/mermaid.js`

- [ ] **Step 1: 创建工具文件并抽取逻辑**

```javascript
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
    if (/^[\w-]+\s+\[.*\]$/.test(title)) return match;
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
```

- [ ] **Step 2: 运行测试**

Run: `npm run lint`
Expected: 成功，无 eslint 错误

- [ ] **Step 3: Commit**

```bash
git add src/utils/mermaid.js
git commit -m "feat: extract mermaid tools to utils"
```

---

### Task 2: 创建公共组件 `MarkdownViewer.jsx`

**Files:**
- Create: `src/components/common/MarkdownViewer.jsx`

- [ ] **Step 1: 创建文件目录与代码**

Run: `mkdir -p src/components/common`

```javascript
// src/components/common/MarkdownViewer.jsx
import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import mermaid from '../../utils/mermaid';
import { sanitizeMermaidSource } from '../../utils/mermaid';
import Icon from '../Icon';

function MermaidDiagram({ content }) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const source = sanitizeMermaidSource(content);

  useEffect(() => {
    let cancelled = false;

    const renderDiagram = async () => {
      if (!source) {
        setSvg('');
        setError('');
        return;
      }

      let renderId = '';
      try {
        renderId = `chat-mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        console.log('[MERMAID_RAW:viewer]', renderId, source);
        const result = await mermaid.render(renderId, source);
        if (result.svg.includes('error in text')) {
          console.warn('[MERMAID_ERROR] "error in text" detected', { renderId, source });
          throw new Error('Mermaid syntax error');
        }
        if (result.svg.length < 200) {
          console.warn('[MERMAID_WARN] SVG unusually small — possible partial render', {
            renderId, svgLength: result.svg.length, svgPreview: result.svg.slice(0, 300)
          });
        }
        if (!cancelled) {
          setSvg(result.svg);
          setError('');
        }
      } catch (err) {
        console.warn('Mermaid render failed, showing source:', err?.message);
        if (!cancelled) {
          setSvg('');
          setError('fallback');
        }
      } finally {
        if (renderId) {
          document.getElementById(renderId)?.remove();
          document.getElementById(`d${renderId}`)?.remove();
        }
      }
    };

    renderDiagram();

    return () => {
      cancelled = true;
    };
  }, [source]);

  if (error) {
    return (
      <pre className="text-xs p-3 bg-slate-100 rounded-lg overflow-x-auto font-mono text-slate-600 border border-slate-200 whitespace-pre-wrap">{source}</pre>
    );
  }

  if (!svg) {
    return <div className="text-slate-400 text-xs py-4 text-center">正在生成可视化图解...</div>;
  }

  return <div className="mermaid-svg-wrapper overflow-x-auto p-2 bg-white rounded-lg border border-slate-100 shadow-inner" dangerouslySetInnerHTML={{ __html: svg }} />;
}

export default function MarkdownViewer({ content, className = '' }) {
  const handleCopy = (text) => {
    navigator.clipboard?.writeText(text).catch(console.error);
  };

  return (
    <div className={`markdown-body break-words leading-[1.7] ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className: codeClassName, children, ...rest }) {
            const match = /language-(\w+)/.exec(codeClassName || '');
            const codeStr = String(children).replace(/\n$/, '');
            
            if (!inline && match) {
              if (match[1] === 'mermaid') {
                return (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 mt-4 mb-2 shadow-sm">
                    <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 font-medium uppercase tracking-wide">
                      <Icon name="schema" className="material-symbols-outlined text-[16px] text-cyan-600"/>
                      <span>图解模式 (Mermaid)</span>
                    </div>
                    <MermaidDiagram content={codeStr} />
                  </div>
                );
              }
              
              return (
                <div className="relative rounded-xl overflow-hidden my-4 group/code shadow-sm border border-slate-200">
                  <div className="flex items-center justify-between px-4 py-2 bg-slate-50 text-slate-500 text-[11px] font-mono uppercase tracking-wider border-b border-slate-200">
                    <span>{match[1]}</span>
                    <button 
                      onClick={() => handleCopy(codeStr)}
                      className="opacity-0 group-hover/code:opacity-100 focus:opacity-100 transition-opacity hover:text-slate-700 flex items-center gap-1 cursor-pointer"
                      title="Copy code"
                    >
                      <Icon name="content_copy" className="material-symbols-outlined text-[14px]"/>
                      Copy
                    </button>
                  </div>
                  <SyntaxHighlighter
                    {...rest}
                    children={codeStr}
                    style={vscDarkPlus}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{ margin: 0, padding: '1rem', borderTopLeftRadius: 0, borderTopRightRadius: 0, fontSize: '13px', lineHeight: '1.5' }}
                  />
                </div>
              );
            }
            
            return (
              <code {...rest} className={`${codeClassName || ''} bg-slate-100 text-cyan-700 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-200`.trim()}>
                {children}
              </code>
            );
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 2: 运行测试**

Run: `npm run lint`
Expected: 成功，无 eslint 错误

- [ ] **Step 3: Commit**

```bash
git add src/components/common/MarkdownViewer.jsx
git commit -m "feat: create common MarkdownViewer component"
```

---

### Task 3: 改造 `ChatMessage.jsx`

**Files:**
- Modify: `src/components/chat/ChatMessage.jsx`

- [ ] **Step 1: 删除旧的渲染逻辑，使用新组件**

```bash
# 在 src/components/chat/ChatMessage.jsx 中进行如下替换：

# 1. 替换顶部 import
# 移除以下行：
# import ReactMarkdown from 'react-markdown';
# import remarkGfm from 'remark-gfm';
# import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
# import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
# import mermaid from 'mermaid';

# 2. 引入 MarkdownViewer 和提取的 sanitizeMermaidSource（用于 diagram 数组的回退处理）
# 添加：
# import MarkdownViewer from '../common/MarkdownViewer';
# import { sanitizeMermaidSource } from '../../utils/mermaid';

# 3. 移除以下块及函数（行 11 - 195 左右）：
# mermaid.initialize(...)
# normalizeMermaidSource(...)
# sanitizeMermaidSource(...)
# function MermaidDiagram(...)

# 4. 移除原有的 <ReactMarkdown ...> 整个代码块（含内部 components 定义），替换为：
# <MarkdownViewer 
#   content={extractModelText(message.content)} 
#   className={isUser ? 'text-white' : 'text-slate-700 text-[15px]'} 
# />

# 5. 修改底部的 diagrams 映射，如果内部还在直接使用原始的 MermaidDiagram 且不在 Markdown 中：
# (原代码) <MermaidDiagram content={extractModelText(diag)} />
# (需修改为不依赖原内置件的方式，最简单是临时补充 import 刚才提取的，或者如果 ChatMessage 里有 diagrams 数组，考虑到 MarkdownViewer 自身也能渲染，可以保留外部对它的使用或将其包装成 markdown code block 交给 MarkdownViewer。
# 由于 ChatMessage.jsx 会用 extractModelText(diag) 放入 `<MermaidDiagram>`，我们可以简单保留原有的 MermaidDiagram 或者通过 <MarkdownViewer content={`\`\`\`mermaid\n${extractModelText(diag)}\n\`\`\``} /> 渲染。

# 为保持行为一致，直接使用 MarkdownViewer:
# {!isUser && message.diagrams && message.diagrams.map((diag, index) => (
#   <MarkdownViewer 
#     key={`diagram-${index}`}
#     content={`\`\`\`mermaid\n${extractModelText(diag)}\n\`\`\``} 
#   />
# ))}
```

- [ ] **Step 2: 运行测试**

Run: `npm run lint && npm run build`
Expected: 成功，无 eslint 和编译错误

- [ ] **Step 3: Commit**

```bash
git add src/components/chat/ChatMessage.jsx
git commit -m "refactor: use MarkdownViewer in ChatMessage"
```

---

### Task 4: 修复 `ResourceDetail.jsx`

**Files:**
- Modify: `src/pages/ResourceDetail.jsx`

- [ ] **Step 1: 删除旧逻辑，添加预处理与新组件**

```bash
# 在 src/pages/ResourceDetail.jsx 中：

# 1. 删除顶部 mermaid import
# 删除： import mermaid from 'mermaid';

# 2. 导入 MarkdownViewer
# 添加： import MarkdownViewer from '../common/MarkdownViewer';

# 3. 移除文件顶部的以下定义（行 21 - 116 左右）：
# normalizeMermaidSource(...)
# mermaid.initialize(...)
# function MermaidDiagram(...)

# 4. 修改 ResourceDetail 渲染逻辑 (大概行 252 - 275)
# 移除 section 标签上的冗余 prose 类，以免样式冲突：
# <section className="max-w-none"> 

# 并在 section 内部上方计算 finalContent：
```

```javascript
// 在返回 JSX 的 <section className="max-w-none"> 内部或渲染前：
let finalContent = getDisplayContent(resource) || '';
if (resource.type === 'mindmap' && !/^```/m.test(finalContent)) {
  finalContent = `\`\`\`mermaid\n${finalContent}\n\`\`\``;
} else if (resource.type === 'code' && !finalContent.includes('```') && !/^#+\s/m.test(finalContent)) {
  finalContent = `\`\`\`\n${finalContent}\n\`\`\``; 
}
```

```bash
# 5. 替换原有的三元运算符渲染逻辑：
# <MarkdownViewer content={finalContent} className="text-[15px] text-slate-700" />
```

- [ ] **Step 2: 运行测试**

Run: `npm run lint && npm run build`
Expected: 成功，无 eslint 和编译错误

- [ ] **Step 3: Commit**

```bash
git add src/pages/ResourceDetail.jsx
git commit -m "fix: use MarkdownViewer for ResourceDetail to fix markdown rendering"
```

---

### Task 5: 记录 WORKFLOW.md

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: 追加日志与 Agenda**

```bash
cat << 'EOF' >> WORKFLOW.md

### 2026-06-17
- **更新文件**: `src/utils/mermaid.js`, `src/components/common/MarkdownViewer.jsx`, `src/components/chat/ChatMessage.jsx`, `src/pages/ResourceDetail.jsx`
- **核心改动**: 提取全局复用的 `MarkdownViewer` 组件解决 `ResourceDetail` Markdown 解析失效问题。将散落的 mermaid 配置统一收拢至工具包，同时彻底清理 ChatMessage 和 ResourceDetail 内部耦合的富文本渲染逻辑。
- **测试结果**: 前端 lint/build 成功。
- **接口漂移**: 无。跨组件接口重构成功。

---

## 全局重构与技术债清理计划 (Agenda)
- [ ] 抽取全局状态管理和重复的 Context
- [ ] 标准化接口请求层（Axios）与统一错误处理
- [ ] 梳理冗余 UI 组件并迁移至统一组件库
EOF
```

- [ ] **Step 2: Commit**

```bash
git add WORKFLOW.md
git commit -m "docs: add markdown refactoring record and agenda to workflow"
```
