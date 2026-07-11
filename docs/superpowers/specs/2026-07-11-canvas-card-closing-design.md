# 2026-07-11 Agent 画布卡片关闭与恢复设计方案

本方案旨在为 Agent 画布中的生成产物卡片添加“自行关闭”和“关闭后找回恢复”功能。
采用用户选择的 **方案 B**：优化版标签页（VSCode/Chrome 风格标签页 + 关闭/找回列表）。

---

## 现状分析与痛点
1. **标签页没有关闭入口**：生成的卡片（Plan, Quiz, Markdown 等）以页签形式挂载在画布顶部，用户无法手动清理已完成或不再需要的卡片。
2. **标签页命名暴露代码类名**：标签直接显示 `CodeSandboxCard` 这种 React 组件类名，不够易读和友好。
3. **图标显示为问号**：`WorkspaceTabs` 默认使用 `insert_drive_file` 图标，但在 `Icon.jsx` 的映射表中未注册该图标，导致回退显示为问号 `?`。

---

## 设计方案详情

### 1. 状态管理与数据解析扩展 (Frontend Context & Parser)
- **前端解析更新**：在 `frontend/src/utils/chatStreamEvents.js` 的 `normalizeArtifact` 中，提取并保存事件中的 `title` 字段：
  ```javascript
  title: artifact.title || null
  ```
- **Context 状态新增**：在 `frontend/src/context/ChatContext.jsx` 中，管理本地会话的已关闭卡片 ID：
  - **新增状态**：`hiddenArtifactIds` (Array) 记录当前隐藏的卡片 ID。
  - **新增方法**：
    - `hideArtifact(id)`：将卡片 ID 存入 `hiddenArtifactIds`。若被隐藏的卡片是当前激活卡片，自动切换到剩余未隐藏的最后一张卡片；若没有剩余卡片，则激活卡片设为 `null`。
    - `restoreArtifact(id)`：从 `hiddenArtifactIds` 中移除卡片 ID，并自动设为当前激活卡片。
  - **生命周期清空**：当切换会话（`activeSession` 变化）或切换课程（`activeCourseId` 变化）时，自动清空 `hiddenArtifactIds` 列表。

### 2. 标签页与画布组件改造 (Components)

#### `AgentWorkspace.jsx`
- 从 `ChatContext` 获取 `hiddenArtifactIds`、`hideArtifact`、`restoreArtifact`。
- 过滤出未隐藏的卡片列表，传递给 `WorkspaceTabs` 组件。
- 若没有未隐藏的卡片，画布展示“暂无生成产物”的默认空状态。

#### `WorkspaceTabs.jsx`
- **标签名字与图标映射**：
  为所有 AgentCard 插件映射易读的默认中文标题与特定 Lucide 图标。如果卡片自带 `props.title` 或 `title`（后端生成），则**优先显示卡片自带的动态标题**，否则使用以下中文映射兜底：
  - `QuizCard` -> 标题：`随堂测试`，图标：`quiz`
  - `Mermaid` -> 标题：`流程拓扑图`，图标：`account_tree`
  - `Markdown` -> 标题：`讲解备忘录`，图标：`description`
  - `StudyPlanCard` -> 标题：`今日学习计划`，图标：`calendar_today`
  - `WeakPointsCard` -> 标题：`薄弱知识点`，图标：`insights`
  - `PathRecommendationCard` -> 标题：`学习路径推荐`，图标：`route`
  - `CodeSandboxCard` -> 标题：`代码实操练习`，图标：`code`
- **Tab 关闭按钮**：
  在每一个页签的文字右侧，增加一个灰色的 `✕` 关闭按钮。点击该按钮触发 `onClose(art.id)`，将卡片隐藏。
- **恢复关闭列表 (Dropdown Menu)**：
  标签栏右侧增加一个恢复按钮 `➕ 找回已关闭 (${count})`，仅在有已隐藏卡片时展示。
  - 点击按钮弹出一个下拉菜单，列出所有已隐藏卡片的中文标题。
  - 点击任意项即可将其恢复（从 `hiddenArtifactIds` 移除，并在画布中重新处于激活状态）。

#### `Icon.jsx`
- 在 `materialToLucide` 映射表中补充 `'insert_drive_file': 'FileText'` 的 fallback 注册，防止任何未知文件类型的图标显示为问号。

### 3. 智能体后端序列化对齐 (Backend Serialization)
- **后端模型更新**：在 `agent_service_v2/src/agent_service_v2/artifacts/schemas.py` 中，修改 `PublishedArtifact.to_event_payload`，使 `artifact_created` 类型的 SSE 事件 payload 中包含 `"title": self.title`：
  ```python
  def to_event_payload(self) -> dict[str, Any]:
      return {
          "artifact": {
              "id": self.id,
              "type": self.type,
              "title": self.title,  # 💡 补齐序列化
              "props": self.props,
          }
      }
  ```

---

## 影响评估
- **纯粹向前兼容**：修改后端 `to_event_payload` 为在 `artifact` 对象中增加一个可选的 `title` 字段，不破坏既有契约，且前端做了健全的兜底解析。
- **无破坏性变动**：原有的 `workspaceArtifacts` 获取逻辑保持不变，确保了历史记录和实时流生成卡片时依然能正常写入。

---

## 验证计划
1. **自动化测试**：
   - 运行前端和后端（Agent Service）单元测试，确保无受损。
   - 新增针对 `ChatContext` 隐藏/恢复逻辑的单元测试。
   - 运行 `agent_service_v2` 的 `test_protocol_adapter.py`，确认 payload 解析中包含 `title`。
2. **人工验证**：
   - 启动前端与后端服务，观察卡片名是否成功转化为中文或智能体生成的动态名字、图标是否正常。
   - 验证卡片右上角 `✕` 隐藏功能是否正常。
   - 验证隐藏所有卡片后画布是否展示空状态。
   - 验证通过右侧的“找回已关闭”菜单能否百分百恢复。
