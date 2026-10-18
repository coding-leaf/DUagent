# 规范化前后端代码质量扫描与架构护栏沉淀

## Goal

构建统一、极速、无痛的代码扫描与质量校验流水线（前端 ESLint + Vite Build，后端及智能体服务 Ruff），修复扫描暴露出的未定义变量与导入死角，并在 Trellis 规范中正式确立“负向红线 + 显式逃生通道（Escape Hatch）”，消除规范维护焦虑与黑盒失控感。

## Requirements

### 1. 前端代码质量与构建扫描标准化 (Frontend Scanner Standard)
- 前端技术栈为 React 19 + JSX + Vite，严禁擅自引入 TypeScript。
- 复用现有的 ESLint 9 (Flat Config) + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`，确保 React Hook 依赖与语法规范受控。
- 固化 `npm run lint` 与 `npm run build` 作为提交前强约束。

### 2. 后端与智能体端引入极速现代化扫描器 Ruff (Python Linters)
- 淘汰旧式笨重且配置复杂的 flake8/pylint，统一采用 Rust 编写的现代化工具 **Ruff**（0.05 秒极速扫描，跨平台原生二进制）。
- 适配 SQLAlchemy 2.0 语法特性（忽略 `E712` 在 ORM 表达式中的误报）。
- 立即修复扫描已发现的真实代码缺陷：
  - `backend/app/api/v1/auth.py` 中缺失 `settings` 导入导致的潜在 `NameError`。
  - `agent_service_v2/src/agent_service_v2/agents/evaluation.py` 中未定义的 `QuizDiagnoseRequest` 作用域问题。
  - 乱序导入与死代码导入自动修正。

### 3. 在 `.trellis/spec/` 中沉淀“负向红线 + 显式逃生通道” (Spec Solidification)
- **Backend Spec**：明确严禁直接调用外部 LLM 接口；如遇必须直连的底层特殊场景，提供显式逃生通道（`# arch-allow: llm-call-override (reason: ...)`）并收敛在 `infrastructure/`。
- **Agent Service Spec**：明确严禁在 Prompt 中硬编码学科/技术栈；明确严禁沙箱动态写脚本解析文件。
- **Frontend Spec**：明确纯 JSX 原生开发红线与 SSE 状态机安全退出机制。

### 4. 统一全仓一键体检规范 (Unified Pre-commit Check)
- 提供统一的一键校验指令，串联前端 `npm run lint`、后端 `ruff check`、智能体服务 `ruff check` 与单元测试。

## Acceptance Criteria

- [ ] 前端 `npm run lint` 与 `npm run build` 执行无任何 Warning / Error。
- [ ] 后端与 Agent Service 成功配置 Ruff 规则，扫描 0 错误（`auth.py` 与 `evaluation.py` 漏洞已彻底修复）。
- [ ] `.trellis/spec/` 下三个子包的规范文件全部补充了清晰的“负向红线”与“显式逃生通道”声明。
- [ ] 提供一键全仓体检命令，方便开发者与 AI 在每次会话收尾时无痛跑通。
