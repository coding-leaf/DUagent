# 网络层统一拦截与全局 Toast 重构 (Option 1)

## 背景
根据 Phase 2 Master Plan 的 Direction 2（提取公共组件 - 网络层），当前 `src/api/client.js` 中缺乏对 401 鉴权失败和全局 API 错误的统一处理。导致在各个页面级组件（如 AdminConsole、StudentProfile）中散落了大量的 `try-catch` 代码及局部的错误状态维护。这不仅产生了冗余的样板代码，还阻碍了我们将巨型组件平滑拆分与提取 Hook。

## 架构选型与设计模式
- **代理模式 (Proxy)** + **拦截器模式 (Interceptor)**：将 Axios 实例作为代理层，收口所有的异常反馈。
- **现代化 UI 库引入 (`sonner`)**：为了不手动制造包含动画与队列状态管理的“巨石轮子”，我们选用 `sonner`。它是现代 React 生态系统中最流行、极简且支持堆叠式 (Stacking) 的 Toast 库，完全契合我们 "ui-ux-pro-max" 的视觉追求，并完美支持脱离 React Context 在纯 JS 文件中作为纯函数调用。

## 设计细节

1. **依赖引入**
   - 依赖项：`npm install sonner`
   - 不增加其他多余依赖。

2. **全局 Toaster 挂载**
   - 在前端入口文件 `src/App.jsx` 的最外层（`<Router>` 内部或同级）挂载 `<Toaster />`。
   - 配置 `Toaster` 支持 `richColors` 与 `top-center` 定位。
   - 路由微调：为了应对未来重定向规则的变化，在 `App.jsx` 中增加 `/login` 作为登录页别名（当前仅有 `/`）。

3. **`client.js` 拦截器改造**
   - 引入 `toast` from `sonner`。
   - **401 Unauthorized 处理**：清空 `localStorage` 的 `access_token`，不弹 toast（跳转本身即为明确反馈），执行 `window.location.href = '/login'`。
   - **403 Forbidden 处理**：调用 `toast.error('权限不足')`。
   - **5xx 服务器错误 处理**：调用 `toast.error('服务器错误，请稍后重试')`。
   - **其他 4xx 状态码**：不全局 toast（防止与页面内组件 catch 触发的内联提示造成双重轰炸），完全交由组件的 catch 处理。
   - 返回 `Promise.reject(error)`。
