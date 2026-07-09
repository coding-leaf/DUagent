# Design Spec: AIChat Tool Activation and Docstring Optimization

This document specifies the design for solving tool activation failures and parameter schema mismatches in the AIChat AgentScope 2.x runtime.

## 1. Problem Statement

1. **Tool Reset Failures**: In the current implementation, every user turn (HTTP POST to `/agent/v2/workbench/chat`) instantiates a new Agent object. By default, the `activated_groups` list in `AgentState` starts empty. If the Agent directly invokes a tool (such as `read_recent_answers`) without first invoking the meta-tool `reset_tools` (which maps to "整理工具状态" in the frontend) to activate the tool group, the invocation fails with a "Tool not available" status (`state="error"`).
2. **Schema Mismatches**: The Python functions for the learning progress tools lack docstrings. Because AgentScope generates the JSON schema for LLMs based on these docstrings, the LLM receives no parameter descriptions. This causes the LLM to pass invalid arguments (such as passing a list of knowledge points instead of a single string, or passing natural language names instead of 32-character node ID hashes), causing validation crashes.

## 2. Proposed Solution

We will implement a two-part optimization:
1. **Default Tool Activation**: We will modify the workbench agent factory to automatically activate all safe/authorized tool groups on agent initialization. This removes the need for the model to issue a redundant `reset_tools` call at the start of a turn, allowing immediate execution of progressive queries.
2. **Docstring Definitions**: We will add clear, standard Python docstrings to all tool functions under `agent_service_v2`. This ensures that the generated schema contains explicit typing, format constraints, and instructions for parameter usage.

---

## 3. Implementation Details

### 3.1. Default Tool Activation in `workbench_factory.py`

In [workbench_factory.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service_v2/src/agent_service_v2/agents/workbench_factory.py):
1. Import `ToolContext` from `agentscope.state._state`.
2. Extract the names of all non-basic tool groups registered on the toolkit:
   ```python
   activated_groups = [g.name for g in toolkit.tool_groups if g.name != "basic"]
   ```
3. Initialize `AgentState` with this pre-populated `tool_context`:
   ```python
   state=AgentState(
       permission_context=build_workbench_permission_context(),
       tool_context=ToolContext(activated_groups=activated_groups)
   )
   ```

### 3.2. Detailed Docstrings in `learning_progress.py`

In [learning_progress.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service_v2/src/agent_service_v2/tools/learning_progress.py), document `read_learning_progress` and `read_recent_answers`:

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

## 4. Verification and Test Strategy

### 4.1. Unit Tests
We will add a new test case in [test_workbench_factory.py](file:///home/yezisama/workspace/workflow/EDUagent/agent_service_v2/tests/test_workbench_factory.py) to assert:
- `agent.state.tool_context.activated_groups` is pre-populated on instantiation.
- The list of default activated groups contains at least `planning` and `learning_progress`.

We will run the existing test suite using pytest to ensure zero regressions:
```bash
cd agent_service_v2 && ./.venv/bin/pytest
```
