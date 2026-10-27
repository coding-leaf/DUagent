# 技术设计方案：个性化讲义Markdown渲染与历史课件补丁

## 1. 架构定位与设计哲学

本设计遵循“契约收敛 + 最小入侵 + 双向闭环”原则：
1. **未来数据生产端（Producer）**：将 `personal_lesson` 生成契约从弱类型、不可执行的“HTML 幻灯片”收敛为平台核心标准的“结构化 Markdown 讲义”，统一公有与私有个性化资源的输出标准。
2. **安全防线守卫（Guardrail）**：在校验层增加对 `<script>` 的防御性拦截，阻断非安全脚本进入落库流。
3. **历史数据消费端（Consumer）**：在前端渲染前增加非破坏性的清洗管道（Sanitization Pipeline），在保障历史数据完整性的同时平铺展示全部内容并去除无效按钮。

---

## 2. 详细技术实现设计

### 2.1 Agent 端 Prompt 与契约改造 (`agent_service_v2`)

#### A. Prompt 结构重构 (`leader_team.py`)
在 `ResourceWorkerAgent.generate_asset` 中，将 `resource_type == "document"` 改造为：
```python
elif resource_type == "document":
    prompt = f"""You are a senior lecturer for {resolved_title or "the course under study"}.
Please generate a comprehensive, structured Markdown lecture tutorial (rich teaching notes) for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

{course_info}
{course_reference_section}
Structure the notes pedagogically:
1. Core Concepts & Theoretical Intuition
2. Key Mechanisms & Syntax Comparisons (use Markdown tables)
3. Concrete, runnable code examples (when technical) with line-by-line explanations
4. Common Pitfalls & Anti-patterns analysis
5. Student Self-check Summary & Checklist

All code examples, structural analysis, and concepts must stay inside the subject of this course; never default to an unrelated language or discipline.
Output format MUST be a strict JSON:
{{
  "title": "Lecture Title in Simplified Chinese",
  "markdown_content": "# {knowledge_point or 'General'}\\n\\n## 1. 核心概念与原理\\n..."
}}

Language & Format Requirements:
1. "title" and the inner Markdown tutorial "markdown_content" (including headers, explanations, tables, code blocks) MUST be fully generated in Simplified Chinese (简体中文).
2. Use standard Markdown formatting only. Absolutely DO NOT generate HTML slides, <script>, or inline DOM event handlers.
"""
```

#### B. 数据提取适配 (`personalized_resource_flow.py`)
在 `ModelResourceContentWriter.write` 中：
```python
if resource_type == "personal_lesson":
    data = await worker.generate_asset("document", chapter, topic, **common)
    raw_content = data.get("markdown_content") or data.get("html_content") or data.get("content") or ""
    return _typed(
        title=data.get("title") or topic,
        content=raw_content,
        description=f"围绕“{topic}”的个性化讲义",
        tags=["lesson"],
    )
```

#### C. 安全校验增强 (`resource_drafts.py`)
在 `validate_typed_resource` 中：
```python
if resource_type in {"personal_lesson", "reading", "lesson"}:
    if "<script" in content.lower():
        hard_failures.append("unsupported_script_tags")
```

---

### 2.2 前端数据清洗与展示补丁 (`frontend`)

#### A. 类型元数据补齐 (`ResourceDetail.jsx`)
在 `TYPE_LABELS` 中增补：
```javascript
const TYPE_LABELS = {
  personal_lesson: '专业课程讲解',
  lesson: '标准讲义',
  diagram: '知识图解',
  ...
};
```

#### B. 历史 HTML 幻灯片平铺清洗管道 (`ResourceDetail.jsx`)
编写 `sanitizeResourceContent(content, type)`：
```javascript
export function sanitizeResourceContent(content, type) {
  if (!content || typeof content !== 'string') return '';
  
  // 仅对包含 HTML slide/deck 结构的遗留内容执行清洗平铺
  if (/<div[^>]+(?:class=['"][^'"]*slide|id=['"]deck)/i.test(content)) {
    let cleaned = content;
    // 1. 移除 script 标签及其中内容
    cleaned = cleaned.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    // 2. 移除 nav 翻页栏及上一页/下一页按钮
    cleaned = cleaned.replace(/<div\b[^>]*id=['"]nav['"][^>]*>[\s\S]*?<\/div>/gi, '');
    // 3. 移除 body 级别的污染样式，保留其他局部样式或转平铺
    cleaned = cleaned.replace(/body\s*\{[^}]*\}/gi, '');
    // 4. 解除 .slide 的 display:none 隐藏属性，改为块级平铺并增加间距
    cleaned = cleaned.replace(/\.slide\s*\{[^}]*\}/gi, '.slide { display: block !important; margin-bottom: 2rem; }');
    // 如果没有自带 .slide 样式覆盖，注入一个微型覆盖样式确保所有 slide 均可见
    if (!cleaned.includes('.slide { display: block')) {
      cleaned = `<style>.slide { display: block !important; margin-bottom: 2rem; }</style>\n` + cleaned;
    }
    return cleaned;
  }
  
  return content;
}
```

---

## 3. 兼容性与回归风险评估

1. **向后兼容性（Backward Compatibility）**：
   - 历史资源无需数据库跑迁移脚本修改已有内容，前端运行时自动无害平铺；
   - 现有的 `diagram`（Mermaid）、`reading`（Markdown）、`example`（代码）完全不受任何影响。
2. **向前兼容性（Forward Compatibility）**：
   - 新生成的 `personal_lesson` 将是纯正 Markdown，不会触发平铺正则，直接走标准 `MarkdownViewer` 极速渲染。
3. **回滚方案（Rollback Plan）**：
   - 纯前端与纯 Agent 的非破坏性逻辑调整，可通过 `git revert` 毫秒级回滚。
