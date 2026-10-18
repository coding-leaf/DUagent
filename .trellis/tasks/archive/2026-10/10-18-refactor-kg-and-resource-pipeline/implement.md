# 实施执行计划 (Implementation Plan)

## 任务拆解与执行阶段 (Phases)

### Phase 1: 智能体端通用规划智能体重构 (Agent Service Core)
- [ ] 1.1 在 `agent_service_v2/src/agent_service_v2/agents/` 下实现通用 `curriculum_planner.py`，彻底拔除 C 语言硬编码，支持学科自适应与 DAG 拓扑自检。
- [ ] 1.2 在 `agent_service_v2/src/agent_service_v2/api/knowledge.py` 中对接新的 `CourseCurriculumPlanner`，保留对老入参的完全兼容。
- [ ] 1.3 编写单元测试验证 `curriculum_planner` 对不同学科大纲的解析与 DAG 输出有效性。

### Phase 2: 原生大纲解析工具实现 (Document Outline Parsers)
- [ ] 2.1 在 `agent_service_v2/src/agent_service_v2/tools/outline_extractor.py` 中实现结构化大纲提取器（支持 Markdown 标题树与 Docx 标题层级）。
- [ ] 2.2 编写单元测试验证大纲提取器对复杂标题、多层级大纲的提取准确率。

### Phase 3: 拔除 Backend 违规调用与统一委托 (Backend Decoupling)
- [ ] 3.1 改造 `backend/app/services/kg_generation.py`：物理删除 `generate_kg_from_llm`，当 `source_type == "outline_text"` 时统一向 Agent Service 发起内部委托。
- [ ] 3.2 验证后端调用 Agent Service 生成知识图谱的完整链路。

### Phase 4: 全量回归测试与质量验证 (Full Regression)
- [ ] 4.1 运行 `agent_service_v2` 全量 `pytest` 测试套件，确保 245 个单测以及新增单测 100% 绿灯。
- [ ] 4.2 运行后端关键服务测试，确保图谱生成与持久化无异常。

---

## 验证与验收指令 (Validation Commands)

```bash
# 1. 验证 agent_service_v2 单测全量通过
cd agent_service_v2
pytest tests/ -v

# 2. 验证新通用规划智能体单测
pytest tests/test_curriculum_planner.py -v

# 3. 验证 backend 移除直接 LLM 调用后导入正常
cd ../backend
.venv/Scripts/python.exe -c "from app.services.kg_generation import generate_knowledge_graph_version; print('Backend kg_generation cleanly decoupled')"
```
