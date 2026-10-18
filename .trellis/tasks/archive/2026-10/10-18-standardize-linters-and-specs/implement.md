# 实施执行计划 (Implementation Plan)

## 任务拆解与执行阶段 (Phases)

### Phase 1: 扫描器规则适配与真实缺陷修复 (Linters & Fixes)
- [ ] 1.1 在根目录或对应子包配置 `ruff.toml` / `pyproject.toml`，排除 SQLAlchemy 的 `E712`，设置精简规则集。
- [ ] 1.2 修复 `backend/app/api/v1/auth.py` 缺失 `settings` 导入的 `NameError` 隐患。
- [ ] 1.3 修复 `agent_service_v2/src/agent_service_v2/agents/evaluation.py` 中 `QuizDiagnoseRequest` 缺失引用的隐患。
- [ ] 1.4 运行 `ruff check --fix` 自动清理无用导入与格式乱序，确保后端与智能体服务 `ruff check` 全部清零通过。
- [ ] 1.5 验证前端 `npm run lint` 与 `npm run build` 保持全绿。

### Phase 2: 沉淀微规范与逃生通道 (Spec Solidification)
- [ ] 2.1 更新 `.trellis/spec/backend/backend/`：写入“严禁直连大模型”红线及 `# arch-allow:` 逃生通道。
- [ ] 2.2 更新 `.trellis/spec/agent_service_v2/backend/`：写入“严禁硬编码学科”与“内置 Tool 解析”红线及配置逃生通道。
- [ ] 2.3 更新 `.trellis/spec/frontend/frontend/`：写入纯 JSX 护栏与 SSE 异常状态安全释放机制。

### Phase 3: 全仓一键检查与验证 (Unified Check & Verification)
- [ ] 3.1 编写 `check_all.sh` / 验证脚本，一键覆盖前后端扫描与单元测试。
- [ ] 3.2 运行全仓质检，确保无回归。

---

## 验证指令 (Validation Commands)

```bash
# 前端扫描
cd frontend && npm run lint && npm run build

# 后端扫描
cd .. && uv run ruff check backend/app/

# 智能体服务扫描
uv run ruff check agent_service_v2/src/agent_service_v2/

# 单测回归
uv run pytest agent_service_v2/tests/
```
