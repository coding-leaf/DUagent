# 修复个性化讲义Markdown渲染异常与历史课件翻页失效补丁

## Goal

修复 Agent 端 `LessonWorkerAgent` 输出原生 HTML 幻灯片代码导致的前端脚本失效、卡死在首页以及 Markdown 格式丢失的问题。将生成规范重构为标准结构化 Markdown 讲义，并在前端增加历史 HTML 课件的清洗平铺与类型标签补丁，实现历史数据与未来生成的双向闭环。

## Background & Problem Statement

在 AI 工作台生成个性化学习资源时，`personal_lesson`（专业课程讲解）存在以下严重体验问题：
1. **翻页与交互失效**：`LessonWorkerAgent` 原 Prompt 要求模型输出 `HTML-based interactive presentation slide deck`，大模型因此输出了包含 `<div class='slide'>`、`<button id='prev'>上一页</button>` 以及原生 `<script>` 的 HTML 片段。前端使用 React + `MarkdownViewer` 渲染，出于安全规则与生命周期规范，React 不会执行内嵌 `<script>`，导致翻页按钮点击毫无反应。
2. **后续内容被永久隐藏**：由于生成的内联 CSS 规定了除首页外 `.slide { display: none }`，在脚本失效后，除第一页外所有易错点精讲内容全部被隐藏，用户无法阅读完整资源。
3. **Markdown 格式与特性丢失**：由于模型生成的是带有 HTML 标签、内联样式和 HTML 转义实体的 Raw HTML，无法享受前端 `MarkdownViewer` 提供的语法高亮、一键复制代码、Mermaid 图解解析与标准排版，甚至污染全局样式。
4. **元数据标签缺失**：前端 `ResourceDetail.jsx` 的 `TYPE_LABELS` 字典中遗漏了 `personal_lesson`，导致顶部徽章退化为泛指的“学习资源”。

## Requirements

### FR-1: Agent 端生成规范重构为标准 Markdown
- 修改 `agent_service_v2/src/agent_service_v2/agents/leader_team.py` 中 `ResourceWorkerAgent.generate_asset` 的 `document` 分支 Prompt：
  - 彻底废除 HTML 幻灯片规范，要求生成结构化、专业、深度详实的 Markdown 讲义教程（涵盖核心概念、原理深度推导、规范对照表、语法高亮代码块、易错陷阱辨析与错题自查清单）。
  - 返回契约统一为 `{"title": "...", "markdown_content": "# ..."}`。
- 在 `agent_service_v2/src/agent_service_v2/generators/personalized_resource_flow.py` 中：
  - `ModelResourceContentWriter.write` 提取 `markdown_content`（兼容 `content` / `html_content`）。

### FR-2: 前端历史课件清洗与平铺渲染
- 在 `frontend/src/pages/ResourceDetail.jsx` 中：
  - 在 `TYPE_LABELS` 补齐 `personal_lesson: '专业课程讲解'`。
  - 增加历史课件清洗适配函数 `sanitizeResourceContent`：
    - 检测内容是否包含 `<div class=['"]slide`、`<div id=['"]deck` 或类似历史 HTML 幻灯片结构。
    - 正则剔除无用的 `<script>...</script>` 脚本块。
    - 正则剔除无用的 `<div id=['"]nav['"]>...</div>` 或死翻页按钮。
    - 覆写其 CSS，将 `.slide { display: none }` 样式替换为正常块级平铺显示，确保所有章节完整可见。
    - 清理可能污染全局 `body` 的原生 `<style>` 标签。

### FR-3: 确定性校验与安全兜底
- 在 `agent_service_v2/src/agent_service_v2/tools/resource_drafts.py` 中：
  - 在 `validate_typed_resource` 中增加对 `personal_lesson`、`reading` 等文档资源的脚本扫描：若检测到 `<script>` 标签，直接判定为 `invalid_script_tags`，阻断非法生成并触发修复重试。

## Acceptance Criteria

- [x] AC-1: `ResourceDetail.jsx` 顶部徽章将 `personal_lesson` 正确识别为“专业课程讲解”。
- [x] AC-2: 数据库现存历史课件（如 `cdc46410bb074398`）在 `ResourceDetail` 中能够完整平铺阅读所有章节与代码，死按钮与死脚本被清洗移除。
- [x] AC-3: `LessonWorkerAgent` / `generate_asset("document")` 生成的内容为标准 Markdown，包含标题、代码块、表格，且绝不包含 HTML `<script>` 或 `<div class='slide'>`。
- [x] AC-4: `agent_service_v2` 单元测试全部通过。
- [x] AC-5: `frontend` 单元测试与端到端代码检查全部通过。
