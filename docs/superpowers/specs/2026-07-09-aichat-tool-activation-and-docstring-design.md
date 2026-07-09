# 设计规范：AIChat 工具激活与 Docstring 优化

本文档详细说明了如何解决 AIChat AgentScope 2.x 运行期工具激活失效以及大模型工具参数 Schema 不匹配的问题。

## 1. 问题背景

1. **工具激活重置失效**：在当前的设计中，每次用户发送消息（POST `/agent/v2/workbench/chat`）都会重新实例化 Agent 对象。默认情况下，`AgentState` 中的 `activated_groups` 列表为空。若 Agent 在本轮对话中直接调用如 `read_recent_answers` 的具体工具，而未首先调用 `reset_tools`（前端对应“整理工具状态”）来激活该工具组，就会导致调用失败（状态为 `error`）。
2. **工具参数 Schema 缺失**：`agent_service_v2` 中已注册的进度和答题工具缺少 Python Docstring 描述。因为 AgentScope 是基于 Docstring 自动提取并生成大模型工具的 JSON Schema，这导致大模型无法获取参数 `node_id` 和 `knowledge_point` 的描述与约束，从而大模型可能会传入错误的参数类型（如合并查询传入了 List，或者将中文节点名当作 `node_id` 传入），导致参数校验崩溃。

## 2. 优化方案

我们将实施以下两项优化：
1. **默认激活安全工具组**：修改工作台 Agent 工厂，在 Agent 初始化时默认激活所有已授权的安全工具组。这避免了模型在每一轮对话开始时都必须浪费一轮交互去调用 `reset_tools`，实现了即开即用。
2. **补全 Docstring 描述**：在 `learning_progress.py` 中为关键工具函数补充清晰的 Google 风格文档注释，定义入参的具体含义和格式限制。

---

## 3. 实现细节

### 3.1. 默认工具激活（修改 `workbench_factory.py`）

在 [workbench_factory.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service_v2/src/agent_service_v2/agents/workbench_factory.py) 中：
1. 导入 `ToolContext` 依赖：
   ```python
   from agentscope.state._state import ToolContext
   ```
2. 动态扫描 `toolkit.tool_groups` 中除了 `basic` 之外的所有已注册安全工具组：
   ```python
   activated_groups = [g.name for g in toolkit.tool_groups if g.name != "basic"]
   ```
3. 在初始化 `Agent` 时，将这些工具组作为初值注入到 `AgentState` 中：
   ```python
   state=AgentState(
       permission_context=build_workbench_permission_context(),
       tool_context=ToolContext(activated_groups=activated_groups)
   )
   ```

### 3.2. 详细 Docstring 补全（修改 `learning_progress.py`）

在 [learning_progress.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service_v2/src/agent_service_v2/tools/learning_progress.py) 中，补全 `read_learning_progress` 和 `read_recent_answers` 的文档描述：

```python
async def read_learning_progress(limit_nodes: int = 50, **_ignored: Any) -> dict[str, Any]:
    """Read the current learner's course progress overview before giving next-step learning advice.

    Args:
        limit_nodes (int): The maximum number of nodes to return in the progress overview. Defaults to 50.
    """
    ...

async def read_recent_answers(
    node_id: str | None = None,
    knowledge_point: str | None = None,
    limit: int = 10,
    only_wrong: bool = True,
    **_ignored: Any,
) -> dict[str, Any]:
    """Read up to 10 recent answer records for a node or knowledge point before explaining mistakes.

    Args:
        node_id (str, optional): The unique 32-character identifier (hash/UUID) of the node (from the progress overview). Do NOT pass the natural language/Chinese node name. Defaults to None.
        knowledge_point (str, optional): The exact name of the knowledge point to query. Defaults to None.
        limit (int): The maximum number of records to return. Defaults to 10.
        only_wrong (bool): Whether to only return incorrect answer records. Defaults to True.
    """
    ...
```

---

## 4. 测试与验证策略

### 4.1. 单元测试
我们将在 [test_workbench_factory.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service_v2/tests/test_workbench_factory.py) 中新增一个测试用例，断言：
- `agent.state.tool_context.activated_groups` 在实例化时已被预装载。
- 默认激活的工具组列表至少包含 `planning` 和 `learning_progress`。

运行整个测试套件以确保无 Regression：
```bash
cd agent_service_v2 && ./.venv/bin/pytest
```
