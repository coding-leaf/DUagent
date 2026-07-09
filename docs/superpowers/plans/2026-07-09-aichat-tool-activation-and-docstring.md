# AIChat Tool Activation and Docstring Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the AIChat agent automatically has its authorized tool groups activated on startup to prevent failures, and has robust docstring-based tool schemas to prevent argument hallucinations.

**Architecture:** Initialize the `AgentState`'s `tool_context.activated_groups` with all registered safe tool groups in the factory, and write complete Google-style docstrings for progressive learning progress tools.

**Tech Stack:** Python, AgentScope 2.x, pytest

---

### Task 1: Pre-activate Safe Tool Groups on Agent Initialization

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Test: `agent_service_v2/tests/test_workbench_factory.py`

- [ ] **Step 1: Write the failing test**

Add this test to `agent_service_v2/tests/test_workbench_factory.py`:

```python
def test_factory_pre_activates_safe_tool_groups(tmp_path: Path):
    class FakeModel:
        pass

    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())
    agent = factory.create_agent(
        user_id="u1",
        course_id="c1",
        workspace=workspace,
        run_id="run-1",
    )
    activated = agent.state.tool_context.activated_groups
    assert "planning" in activated
    assert "learning_progress" in activated
    assert "learning_state" in activated
    assert "artifact" in activated
    assert "review" in activated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workbench_factory.py::test_factory_pre_activates_safe_tool_groups -v`
Expected: FAIL with `AssertionError: assert 'planning' in []`

- [ ] **Step 3: Implement minimal code to make it pass**

Modify `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`:
1. Add import:
   `from agentscope.state._state import ToolContext`
2. Update `create_agent` to extract and pre-activate all non-basic tool groups:
   ```python
        learning_client = build_backend_learning_client_from_settings()
        learning_progress_tools = build_learning_progress_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
        )
        toolkit = Toolkit(
            tool_groups=build_workbench_tool_groups(
                memory_tools=[],
                rag_tools=[],
                learning_progress_tools=learning_progress_tools,
                workspace=workspace,
                run_id=run_id,
            )
        )
        activated_groups = [g.name for g in toolkit.tool_groups if g.name != "basic"]
   ```
3. Inject the `tool_context` into the `AgentState`:
   ```python
        return Agent(
            name=_agent_name(course_id),
            system_prompt=_system_prompt(user_id=user_id, course_id=course_id),
            model=model,
            toolkit=toolkit,
            middlewares=middlewares,
            state=AgentState(
                permission_context=build_workbench_permission_context(),
                tool_context=ToolContext(activated_groups=activated_groups)
            ),
            offloader=workspace,
            context_config=ContextConfig(tool_result_limit=20000),
            react_config=ReActConfig(max_iters=12),
        )
   ```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workbench_factory.py::test_factory_pre_activates_safe_tool_groups -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_service_v2/agents/workbench_factory.py tests/test_workbench_factory.py
git commit -m "feat: pre-activate safe tool groups in agent factory"
```

---

### Task 2: Document Learning Progress Tools with Google-style Docstrings

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/learning_progress.py`
- Test: `agent_service_v2/tests/test_learning_progress_tools.py`

- [ ] **Step 1: Write the failing test**

Add this test to `agent_service_v2/tests/test_learning_progress_tools.py`:

```python
def test_learning_tools_have_parameter_descriptions():
    client = FakeClient()
    tools = build_learning_progress_tools(client=client, user_id="u1", course_id="c1")
    
    # Check read_recent_answers schema
    tool = next(item for item in tools if item.name == "read_recent_answers")
    schema = tool.input_schema
    properties = schema.get("properties", {})
    
    assert "node_id" in properties
    assert "description" in properties["node_id"]
    assert len(properties["node_id"]["description"]) > 10
    
    assert "knowledge_point" in properties
    assert "description" in properties["knowledge_point"]
    assert len(properties["knowledge_point"]["description"]) > 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_learning_progress_tools.py::test_learning_tools_have_parameter_descriptions -v`
Expected: FAIL with `KeyError: 'description'` (since the docstring is missing and schema has no descriptions).

- [ ] **Step 3: Implement minimal code to make it pass**

Add Google-style docstrings to `read_learning_progress` and `read_recent_answers` in `agent_service_v2/src/agent_service_v2/tools/learning_progress.py`:

```python
    async def read_learning_progress(limit_nodes: int = 50, **_ignored: Any) -> dict[str, Any]:
        """Read the current learner's course progress overview before giving next-step learning advice.

        Args:
            limit_nodes (int): The maximum number of nodes to return in the progress overview. Defaults to 50.
        """
        if client is None:
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
        if client is None:
            ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_learning_progress_tools.py::test_learning_tools_have_parameter_descriptions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_service_v2/tools/learning_progress.py tests/test_learning_progress_tools.py
git commit -m "docs: add Google-style docstrings to learning progress tools"
```
