# EDUagent Frontend

React + Vite 前端，负责学生学习、教师学情和管理员控制台，并通过 Backend 的 `/api/v1` 接口访问业务能力。

## 目录

```text
src/
  api/          Backend API 客户端与服务封装
  components/   可复用展示组件
  context/      用户与课程上下文
  pages/        页面容器
  hooks/        数据获取与页面逻辑
e2e/            Playwright 端到端测试
```

## 本地运行

```bash
npm install
VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev
```

Mock 演示：

```bash
VITE_USE_MOCK=true npm run dev
```

## 检查

```bash
npm run lint
npm run build
npm run test:e2e
```

端到端测试依赖已启动的 Backend、Agent Service、测试数据库和种子数据。

## 接口契约

- Client API：`../docs/10-client-api/Client-API.openapi.json`
- Agent Service API：`../docs/20-agent-api/Agent-Service.openapi.json`

前端只调用 Backend；不得直接访问 Agent Service 或自行扩展未声明的接口字段。
