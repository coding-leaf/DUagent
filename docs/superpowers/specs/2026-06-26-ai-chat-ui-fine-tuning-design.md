# AI Chat UI 视觉微调与 Mock 卡片扩展设计文档

## 背景 (Background)
在完成 AI Chat UI 重构的基础三栏布局（历史记录-工作区-对话栏）后，实际渲染效果与概念设计图在细节精致度、卡片种类以及 Mock 调试工具上存在一些差距：
1. 聊天侧边栏在桌面端显得较窄（380px），代码块阅读体验不佳。
2. 历史侧边栏的半圆折叠按钮浮空压在工作区边缘，发生重叠。
3. 扩展工具按钮（`data_object`）显示为问号，且目前只绑定了 QuizCard 的触发，缺少其他卡片及高保真业务卡片的预览手段。

## 目标与范围 (Scope)
* **包含 (In Scope)**:
  * 调大聊天侧边栏宽度至 `450px`。
  * 修复折叠按钮定位与遮挡。
  * 在 `Icon.jsx` 补齐映射。
  * 扩展 Mock 触发器：以 Popover 浮层菜单形式支持 6 类卡片的渲染测试（测验、流程图、Markdown、学习计划、薄弱点、路径）。
  * 实现 3 种高保真业务组件：`StudyPlanCard`、`WeakPointsCard`、`PathRecommendationCard`。
* **不包含 (Out of Scope)**:
  * 后端数据对接与流解析。

## 详细设计 (Detailed Design)

### 1. 样式修补与宽度调整
- `ChatArea.jsx` 宽度修改为：`w-full lg:w-[450px]`，优化聊天和代码阅读空间。
- `SidebarHistory.jsx` 折叠按钮类加入 `border border-slate-200 shadow-sm z-40 bg-white right-[-12px]`，确保贴合边缘且层级正确。

### 2. 插件注册表扩充
在 `src/components/workspace/PluginRegistry.js` 中增加以下三个高保真组件的映射：
```javascript
import StudyPlanCard from './plugins/StudyPlanCard';
import WeakPointsCard from './plugins/WeakPointsCard';
import PathRecommendationCard from './plugins/PathRecommendationCard';

export const PluginRegistry = {
  // ...
  StudyPlan: StudyPlanCard,
  WeakPoints: WeakPointsCard,
  PathRecommendation: PathRecommendationCard
};
```

### 3. 新增业务卡片样式
* **StudyPlanCard**：以绿色圆圈序号渲染多条学习任务列表，右上角标明总时长，右下角提供“开始练习”行动按钮。
* **WeakPointsCard**：红（低 mastery）、橙（中 mastery）、绿（高 mastery）三色进度条显示核心薄弱点及其影响程度。
* **PathRecommendationCard**：横向时间轴，将步骤以节点横向链接渲染。

### 4. Popover 调试控制器
在 `ChatArea` 的输入框左下角，把原有的 `data_object` 图标替换为大括号 `Braces` 图标作为触发点。点击后弹出悬浮菜单，提供各卡片的触发 Mock 按钮，通过 `sendMockArtifact` 更新状态。
