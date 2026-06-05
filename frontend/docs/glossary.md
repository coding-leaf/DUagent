# Frontend Glossary

本文档记录前端协作中高频且容易混淆的术语。

## Client API

Frontend 与 Backend 之间的浏览器侧接口契约。正式来源是 `../../docs/10-client-api/*`。

## Agent API

Backend 与 Agent Service 之间的内部接口契约。Frontend 不直接调用 Agent API，只在判断某个页面能力是否需要 Agent 数据来源时参考 `../../docs/20-agent-api/*`。

## 契约缺口

页面目标需要某个字段、接口、状态枚举或数据来源，但当前正式 Client API 没有声明，或声明不足以支持正确实现。

契约缺口不能通过前端硬编码、Mock 假数据或推测响应结构解决。

## 阶段一

现有 Client API 主链路收口阶段。目标是让真实 Backend API 下的登录、课程、资源、学习路径、Quiz、AI Chat、教师基础学情和管理员基础页面可运行、可验证。

## 阶段二

契约审查和完整页面能力对齐阶段。目标是明确哪些页面能力需要 Client API、Backend SQL、Backend 聚合逻辑或 Agent API 支撑，再进入实现。

## Mock

本地演示和断网调试用数据层。Mock 不是正式契约来源，也不能证明某字段已经可用。

## Empty/Unknown 状态

真实 Backend 返回空数组、空对象或空值时的前端展示策略。用于诚实呈现数据缺失，不用假数据覆盖问题。

## 页面字段报告

指 `../前端页面字段与布局结构数据报告.md`。该文档描述完整页面设想和布局字段，是阶段二契约审查输入，不是当前实现契约。
