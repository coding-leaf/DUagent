# EduAgent Frontend

React + Vite 前端应用，负责学生端学习流程、教师端学情查看、管理员基础控制台，以及与 Backend `/api/v1` 的浏览器侧集成。

## 当前状态

- 当前处于前后端阶段一联调收口阶段。
- 默认以真实 Backend API 为准，Mock 仅作为本地演示和断网调试手段。
- 阶段一目标不是补齐全部产品页面，而是打通现有 Client API 能承接的主链路。
- 当前前端完整页面目标已经超过现有 Client API 规范的承载范围；超出部分进入阶段二契约审查，不应继续靠硬编码或假数据补齐。
- Playwright E2E 已建立，但仍需在测试数据库、种子数据、Backend、Agent Service 全部就绪后作为最终验收。

## 先看什么

1. `../docs/10-client-api/*`
   - 当前正式 Client API 契约，但不足以承载完整前端目标。
2. `README.md`
   - 前端模块入口、运行方式和阅读顺序。
3. `docs/goals.md`
   - 前端职责边界、一阶段目标、二阶段目标。
4. `docs/decisions.md`
   - 稳定决策，尤其是当前 Client API 不足以承载完整前端目标的判断。
5. `docs/glossary.md`
   - 高频术语定义，避免契约、Mock、阶段目标混用。
6. `docs/temporary-implementation.md`
   - 当前临时约束、已知限制和替换条件。
7. `WORKFLOW.md`
   - 当前阶段状态、最近验证、下一步。
8. `AGENTS.md`
   - 前端协作规则、修改约束、契约纪律。
9. `DESIGN.md`
   - 视觉设计系统草案。
10. `前端页面字段与布局结构数据报告.md`
   - 页面设想和阶段二契约审查输入，不是当前实现契约。

## 关键目录

```text
src/
  api/
    client.js              # Axios 实例，读取 VITE_API_BASE_URL
    services/              # 按业务模块封装 Backend API
    mock/                  # VITE_USE_MOCK=true 时启用
  components/              # Navbar、ProtectedRoute、FeedbackStatus 等通用组件
  context/                 # AuthContext、CourseContext
  pages/                   # 页面级组件
e2e/
  specs.spec.js            # 阶段一主链 E2E
playwright.config.js       # E2E 配置
```

## 运行方式

安装依赖：

```bash
npm install
```

真实后端联调：

```bash
VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev
```

Mock 演示：

```bash
VITE_USE_MOCK=true npm run dev
```

质量检查：

```bash
npm run lint
npm run build
```

E2E：

```bash
npm run test:e2e
```

E2E 依赖测试数据库和种子数据。当前约定由 `backend/scripts/seed_e2e_data.py` 创建固定测试账号、课程、资源、题库、画像、评估和学习路径数据。

## 契约纪律

- 正式前端契约以项目根目录 `../docs/10-client-api/*` 为准。
- Agent 间接契约仅在判断前端变更是否影响 Agent API 时参考项目根目录 `../docs/20-agent-api/*`。
- `frontend/docs/` 如存在同名文档、历史副本或归档资料，不是正式契约源。
- 前端不得因为页面需要自行发明响应字段。
- 如果后端返回空数组或空值，优先展示 Empty/Unknown 状态，不回退到假数据。
- `weak_points` 和 `recent_activity` 是正式 `StudentLearning` 字段；如果后端为空，这是实现或数据来源问题，不是契约缺失。
