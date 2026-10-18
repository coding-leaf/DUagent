# 技术架构与设计方案 (Technical Design)

## 1. 扫描器技术选型对比与决策

| 模块 | 推荐工具 | 理由 | 替代方案及弃用原因 |
| :--- | :--- | :--- | :--- |
| **前端 (React 19 + JSX)** | **ESLint 9 (Flat Config) + Vite Build** | 项目已内置，零新增体积；精准捕获 React 19 Hooks 依赖死锁与 JSX 语法错误；Vite Build 校验 Rollup AST。 | Biome（虽快但需引入新配置）、Vue-tsc（非 Vue 项目不适用且当前不用 TS）。 |
| **后端 (FastAPI + SQLA 2.0)** | **Ruff 0.13+** | Rust 构建，0.05 秒瞬时完成整个后端的 AST 语法、未定义变量、未引用导入扫描；原生支持 Windows。 | Flake8/Pylint（速度慢 50-100 倍，且 Windows 上多进程配置复杂）。 |
| **智能体 (AgentScope 2.x)** | **Ruff 0.13+** | 与后端统一工具链，可配置在 `pyproject.toml` 中，直接用 `uv run ruff check` 驱动。 | Black + isort（格式化和 lint 分离，且无法检查未定义变量）。 |

---

## 2. Ruff 规则适配与 ORM 兼容设计

在 `pyproject.toml` 或 `ruff.toml` 中配置规则集：
- `select = ["E", "F", "W", "I"]`（语法错误、未定义变量、警告、导入排序）
- `ignore = ["E712", "E501"]`：
  - `E712`：SQLAlchemy 2.0 中 `Model.is_deleted == False` 是标准的 SQL 二元表达式，Pythonic 的 `not is_deleted` 会破坏 SQLAlchemy 生成的 SQL，因此必须全局豁免 `E712`。
  - `E501`：单行长度由格式化控制，不阻断静态扫描。

---

## 3. 架构红线与显式逃生通道规范设计

在 `.trellis/spec/` 统一建立格式规范：

```markdown
### 架构红线 (Hard Negative Constraints)
- ❌ 严禁 [某行为]：[原因与标准替代做法]

### 逃生通道 (Escape Hatches)
- 若遇特殊基础设施场景必须例外，必须满足：
  1. 仅限收敛于 `app/infrastructure/`，严禁在业务服务层分散；
  2. 显式添加注解 `# arch-allow: <tag> (reason: <说明>)`，未经声明的直连将被拒绝。
```
