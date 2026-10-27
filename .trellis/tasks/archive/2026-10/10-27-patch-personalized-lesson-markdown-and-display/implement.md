# 实施计划：个性化讲义Markdown渲染与历史课件补丁

## 1. 实施检查清单

- [x] **Step 1: Agent 服务端生成契约重构**
  - [x] 1.1 修改 `agent_service_v2/src/agent_service_v2/agents/leader_team.py` 中的 `document` Prompt 为标准结构化 Markdown 讲义。
  - [x] 1.2 修改 `agent_service_v2/src/agent_service_v2/generators/personalized_resource_flow.py`，支持提取 `markdown_content` 并标注清晰描述。
  - [x] 1.3 在 `agent_service_v2/src/agent_service_v2/tools/resource_drafts.py` 增加 `<script>` 标签拦截校验。
  - [x] 1.4 运行 `agent_service_v2` 测试验证无回归。

- [x] **Step 2: 前端展示补丁与历史数据清洗**
  - [x] 2.1 修改 `frontend/src/pages/ResourceDetail.jsx`，在 `TYPE_LABELS` 补齐 `personal_lesson: '专业课程讲解'`。
  - [x] 2.2 在 `ResourceDetail.jsx` 编写并应用 `sanitizeResourceContent`，清洗旧数据中的 `<script>` 与翻页按钮，平铺展开所有 `.slide`。
  - [x] 2.3 编写前端单元测试，验证 `sanitizeResourceContent` 与 `ResourceDetail` 渲染表现。
  - [x] 2.4 运行前端测试验证通过。

- [x] **Step 3: 综合真实环境与全量回归验证**
  - [x] 3.1 验证数据库实际记录 `cdc46410bb074398` 在清洗后能正常完整展示全部 3 个易错点小节，死按钮完全消除。
  - [x] 3.2 运行全项目质量门禁（Ruff / Pytest / Vitest）。

---

## 2. 验证命令

```bash
# Agent Service 单元测试
pytest agent_service_v2/tests/test_leader_team.py agent_service_v2/tests/test_personalized_resource_flow.py

# Frontend 单元测试
cd frontend && npm test -- src/pages/ResourceDetail.test.jsx
```
