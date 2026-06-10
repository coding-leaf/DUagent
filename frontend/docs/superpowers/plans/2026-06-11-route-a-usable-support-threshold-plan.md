# Route A Usable Support Threshold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change Route A KG pruning from a strict `0.70` support gate to a usable `0.60` active-KG gate while preserving strong/good/weak/unsupported metrics for later ready-gate decisions.

**Architecture:** Keep Agent grounding output unchanged and implement the change entirely in Backend's pure pruning layer and KG generation CLI. The pruning threshold remains caller-controlled for compatibility, but the new support-band metrics are always computed over all candidate nodes with fixed `0.60/0.65/0.70` bands.

**Tech Stack:** Python 3.11+, FastAPI backend utilities, SQLAlchemy async ORM, pytest, MySQL-only real verification, existing versioned `CourseKnowledgeGraph` persistence.

---

## Scope And Preconditions

Source spec:

- `frontend/docs/superpowers/specs/2026-06-11-route-a-usable-support-threshold-design.md`

User clarifications to preserve:

- `body_support_pass_ratio` remains tied to the caller-provided `threshold`.
- `usable_support_ratio` is fixed to `0.60` and can differ from `body_support_pass_ratio` when `threshold != 0.60`.
- `strong_node_count`, `good_node_count`, `weak_but_usable_node_count`, and `unsupported_node_count` are computed over all candidate nodes, not only kept nodes.
- `pruned_nodes` can remain a full detail list in this round; record the future large-graph risk in progress docs.

Execution precondition:

- This plan modifies `../backend/*` and frontend progress docs. If running from the current `frontend/` sandbox, request write permission for `../backend` or switch to a workspace where backend is writable.
- Do not modify `../docs/10-client-api/*`; this round does not change Client API or OpenAPI.
- Real sample generation must use MySQL only. Do not use SQLite for the Route A real-data verification.

## Code Modification Pre-Review

**问题分析**

Current Backend Route A pruning defaults to `threshold=0.70`, so the latest C-language v3 grounding sample keeps only strong nodes and still produces a fragmented active KG. The new product decision is to keep `>=0.60` nodes in the active KG while retaining banded metrics so downstream gates can distinguish strong support from merely usable support.

**计划修改的文件**

- `../backend/app/services/kg_body_grounding.py`
- `../backend/tools/generate_knowledge_graph.py`
- `../backend/tests/test_kg_body_grounding.py`
- `../backend/tests/test_generate_kg.py`
- `../backend/WORKFLOW.md`
- `WORKFLOW.md`
- `docs/feature-ledger.md`

**修改方案**

- Add fixed support thresholds and a support-band classifier in Backend pruning service.
- Change `filter_supported_knowledge_graph()` default threshold to `0.60`.
- Keep pruning controlled by the function's `threshold` argument.
- Compute all support-band counts over the complete candidate node list.
- Add compatibility metrics and new metrics in one metrics JSON.
- Change CLI `--grounding-threshold` default to `0.60`.
- Use `generation_strategy=route_a_prune_usable_060` only when the supplied threshold is effectively `0.60`; keep `route_a_prune_unsupported` for explicit non-default thresholds.
- Update workflow/ledger docs after verification, including the deferred `pruned_nodes` growth risk.

**可能影响的功能**

- Backend KG generation CLI with `--grounding-file`.
- Versioned `CourseKnowledgeGraph.metrics` content for Route A generated graphs.
- LearningPath active KG consumers indirectly benefit from the new active KG once generated.
- No Frontend UI, Client API, Agent HTTP API, Qdrant data, upload files, or OpenAPI contract changes.

**计划运行的测试命令**

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Real sample verification command, only if the `/tmp/kg-resource-probe/*v3.json` files and MySQL dev DB are available:

```bash
cd ../backend
set -a
. ../agent_service/.env
set +a
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python tools/generate_knowledge_graph.py \
  --course-id 6c698badb60a4809 \
  --kg-json /tmp/kg-resource-probe/c-language-active-kg-v1.json \
  --grounding-file /tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json \
  --grounding-threshold 0.60 \
  --auto
```

Expected real sample outcome:

- New active graph uses `source_type=route_a_body_grounded`.
- New active graph uses `generation_strategy=route_a_prune_usable_060`.
- `metrics.support_band_counts == {"strong": 57, "good": 34, "weak_but_usable": 17, "unsupported": 8}`.
- `candidate_node_count == 116`, `kept_node_count == 108`, `pruned_node_count == 8`.
- Edge count is materially higher than the old Route A `22 nodes / 2 edges`.

## File Structure

Backend:

- Modify `../backend/app/services/kg_body_grounding.py`
  - Own fixed thresholds, band classification, pruning, edge filtering, and metrics construction.
- Modify `../backend/tools/generate_knowledge_graph.py`
  - Own CLI defaults, parser construction, grounding-file pruning wrapper, and generation strategy selection.

Tests:

- Modify `../backend/tests/test_kg_body_grounding.py`
  - Cover default `0.60` behavior, explicit `0.70` compatibility behavior, zero candidates, duplicate matches, shallow copies, and all new metrics.
- Modify `../backend/tests/test_generate_kg.py`
  - Cover grounding-file pruning with default usable threshold, explicit strict threshold compatibility, parser default, and generation strategy selection.

Progress docs:

- Modify `../backend/WORKFLOW.md`
  - Record Backend Route A threshold change, test evidence, real sample evidence if run, and deferred `pruned_nodes` size risk.
- Modify `WORKFLOW.md`
  - Record frontend workspace project progress because this is the main project steering log.
- Modify `docs/feature-ledger.md`
  - Update the current KG next-step queue after the usable-threshold Route A version is generated or after code-only verification if real sample could not be run.

## Task 1: Backend Pruning Metrics Tests

**Files:**

- Modify: `../backend/tests/test_kg_body_grounding.py`
- Later modify: `../backend/app/services/kg_body_grounding.py`

- [ ] **Step 1: Write the failing default-threshold and band metrics test**

In `../backend/tests/test_kg_body_grounding.py`, replace the current `test_filter_supported_knowledge_graph_prunes_nodes_edges_and_metrics` body with this version:

```python
def test_filter_supported_knowledge_graph_defaults_to_usable_threshold_and_support_bands() -> None:
    nodes = [
        {"id": "node-1", "name": "变量", "chapter": "第一章"},
        {"id": "node-2", "name": "指针", "chapter": "第二章"},
        {"id": "node-3", "name": "数组", "chapter": "第三章"},
        {"id": "node-4", "name": "结构体", "chapter": "第四章"},
        {"id": "node-5", "name": "文件", "chapter": "第五章"},
    ]
    edges = [
        {"from": "node-1", "to": "node-2"},
        {"from": "node-2", "to": "node-3"},
        {"from": "node-3", "to": "node-4"},
        {"from": "node-4", "to": "node-5"},
    ]
    matches = [
        GroundingMatch(
            node_id="node-1",
            score=0.72,
            chunk_id="chunk-strong",
            content_preview="变量用于保存程序运行过程中的数据。",
        ),
        GroundingMatch(
            node_id="node-2",
            score=0.66,
            chunk_id="chunk-good",
            content_preview="指针保存对象的地址。",
        ),
        GroundingMatch(
            node_id="node-3",
            score=0.62,
            chunk_id="chunk-weak",
            content_preview="数组是一组连续元素。",
        ),
        GroundingMatch(
            node_id="node-4",
            score=0.59,
            chunk_id="chunk-low",
            content_preview="结构体候选低于可用阈值。",
        ),
    ]

    filtered_nodes, filtered_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        edges,
        matches,
    )

    assert filtered_nodes == nodes[:3]
    assert filtered_edges == [
        {"from": "node-1", "to": "node-2"},
        {"from": "node-2", "to": "node-3"},
    ]
    assert metrics == {
        "body_top1_threshold": 0.60,
        "usable_support_threshold": 0.60,
        "good_support_threshold": 0.65,
        "strong_support_threshold": 0.70,
        "candidate_node_count": 5,
        "kept_node_count": 3,
        "pruned_node_count": 2,
        "body_support_pass_ratio": 0.6,
        "usable_support_ratio": 0.6,
        "strong_support_ratio": 0.2,
        "good_or_strong_support_ratio": 0.4,
        "strong_node_count": 1,
        "good_node_count": 1,
        "weak_but_usable_node_count": 1,
        "unsupported_node_count": 2,
        "support_band_counts": {
            "strong": 1,
            "good": 1,
            "weak_but_usable": 1,
            "unsupported": 2,
        },
        "pruned_nodes": [
            {
                "node_id": "node-4",
                "node_name": "结构体",
                "chapter": "第四章",
                "body_top1_score": 0.59,
                "chunk_id": "chunk-low",
                "content_preview": "结构体候选低于可用阈值。",
            },
            {
                "node_id": "node-5",
                "node_name": "文件",
                "chapter": "第五章",
                "body_top1_score": None,
                "chunk_id": None,
                "content_preview": "",
            },
        ],
    }
```

- [ ] **Step 2: Write the failing explicit-threshold compatibility test**

Add this test in `../backend/tests/test_kg_body_grounding.py` after the default-threshold test:

```python
def test_filter_supported_knowledge_graph_explicit_threshold_preserves_pass_ratio_but_counts_all_bands() -> None:
    nodes = [
        {"id": "node-1", "name": "变量", "chapter": "第一章"},
        {"id": "node-2", "name": "指针", "chapter": "第二章"},
        {"id": "node-3", "name": "数组", "chapter": "第三章"},
        {"id": "node-4", "name": "结构体", "chapter": "第四章"},
    ]
    matches = [
        GroundingMatch(
            node_id="node-1",
            score=0.82,
            chunk_id="chunk-a",
            content_preview="变量用于保存程序运行过程中的数据。",
        ),
        GroundingMatch(
            node_id="node-2",
            score=0.70,
            chunk_id="chunk-b",
            content_preview="指针保存对象的地址。",
        ),
        GroundingMatch(
            node_id="node-3",
            score=0.62,
            chunk_id="chunk-c",
            content_preview="数组是一组连续元素。",
        ),
    ]

    filtered_nodes, filtered_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        [{"from": "node-1", "to": "node-2"}, {"from": "node-2", "to": "node-3"}],
        matches,
        threshold=0.70,
    )

    assert filtered_nodes == nodes[:2]
    assert filtered_edges == [{"from": "node-1", "to": "node-2"}]
    assert metrics["body_top1_threshold"] == 0.70
    assert metrics["kept_node_count"] == 2
    assert metrics["pruned_node_count"] == 2
    assert metrics["body_support_pass_ratio"] == 0.5
    assert metrics["usable_support_ratio"] == 0.75
    assert metrics["strong_support_ratio"] == 0.5
    assert metrics["good_or_strong_support_ratio"] == 0.5
    assert metrics["strong_node_count"] == 2
    assert metrics["good_node_count"] == 0
    assert metrics["weak_but_usable_node_count"] == 1
    assert metrics["unsupported_node_count"] == 1
    assert metrics["support_band_counts"] == {
        "strong": 2,
        "good": 0,
        "weak_but_usable": 1,
        "unsupported": 1,
    }
```

This test encodes the user clarification: with `threshold=0.70`, `body_support_pass_ratio` is `2/4`, while fixed `usable_support_ratio` is `3/4`.

- [ ] **Step 3: Update the zero-candidate expected metrics**

In `test_filter_supported_knowledge_graph_handles_zero_candidate_nodes`, update the exact expected metrics to:

```python
    assert metrics == {
        "body_top1_threshold": 0.60,
        "usable_support_threshold": 0.60,
        "good_support_threshold": 0.65,
        "strong_support_threshold": 0.70,
        "candidate_node_count": 0,
        "kept_node_count": 0,
        "pruned_node_count": 0,
        "body_support_pass_ratio": 0.0,
        "usable_support_ratio": 0.0,
        "strong_support_ratio": 0.0,
        "good_or_strong_support_ratio": 0.0,
        "strong_node_count": 0,
        "good_node_count": 0,
        "weak_but_usable_node_count": 0,
        "unsupported_node_count": 0,
        "support_band_counts": {
            "strong": 0,
            "good": 0,
            "weak_but_usable": 0,
            "unsupported": 0,
        },
        "pruned_nodes": [],
    }
```

- [ ] **Step 4: Run tests and verify RED**

Run:

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_kg_body_grounding.py -q
```

Expected:

- FAIL because `body_top1_threshold` is still `0.70` by default or the new metrics keys do not exist.
- Do not change production code until this failing test is observed.

## Task 2: Backend Pruning Implementation

**Files:**

- Modify: `../backend/app/services/kg_body_grounding.py`
- Test: `../backend/tests/test_kg_body_grounding.py`

- [ ] **Step 1: Add constants and helpers**

In `../backend/app/services/kg_body_grounding.py`, add these constants below `_TOC_LINE_PATTERNS`:

```python
USABLE_SUPPORT_THRESHOLD = 0.60
GOOD_SUPPORT_THRESHOLD = 0.65
STRONG_SUPPORT_THRESHOLD = 0.70

SUPPORT_BAND_STRONG = "strong"
SUPPORT_BAND_GOOD = "good"
SUPPORT_BAND_WEAK_BUT_USABLE = "weak_but_usable"
SUPPORT_BAND_UNSUPPORTED = "unsupported"
```

Add these helpers above `filter_supported_knowledge_graph()`:

```python
def _support_band(score: float | None) -> str:
    if score is None or score < USABLE_SUPPORT_THRESHOLD:
        return SUPPORT_BAND_UNSUPPORTED
    if score >= STRONG_SUPPORT_THRESHOLD:
        return SUPPORT_BAND_STRONG
    if score >= GOOD_SUPPORT_THRESHOLD:
        return SUPPORT_BAND_GOOD
    return SUPPORT_BAND_WEAK_BUT_USABLE


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator > 0 else 0.0
```

- [ ] **Step 2: Change pruning default and metrics construction**

Update the `filter_supported_knowledge_graph()` signature:

```python
def filter_supported_knowledge_graph(
    nodes: Iterable[dict[str, Any]],
    edges: Iterable[dict[str, Any]],
    matches: Iterable[GroundingMatch],
    threshold: float = USABLE_SUPPORT_THRESHOLD,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
```

Inside the function, replace the kept/pruned loop and metrics block with this implementation:

```python
    kept_nodes: list[dict[str, Any]] = []
    pruned_nodes: list[dict[str, Any]] = []
    support_band_counts = {
        SUPPORT_BAND_STRONG: 0,
        SUPPORT_BAND_GOOD: 0,
        SUPPORT_BAND_WEAK_BUT_USABLE: 0,
        SUPPORT_BAND_UNSUPPORTED: 0,
    }

    for node in node_list:
        node_id = str(node.get("id", ""))
        match = match_by_node_id.get(node_id)
        score = match.score if match is not None else None
        support_band_counts[_support_band(score)] += 1

        if match is not None and match.score >= threshold:
            kept_nodes.append(dict(node))
            continue

        pruned_nodes.append(
            {
                "node_id": node_id,
                "node_name": node.get("name", ""),
                "chapter": node.get("chapter", ""),
                "body_top1_score": score,
                "chunk_id": match.chunk_id if match is not None else None,
                "content_preview": match.content_preview if match is not None else "",
            }
        )
```

Replace the metrics block with:

```python
    candidate_node_count = len(node_list)
    kept_node_count = len(kept_nodes)
    strong_node_count = support_band_counts[SUPPORT_BAND_STRONG]
    good_node_count = support_band_counts[SUPPORT_BAND_GOOD]
    weak_but_usable_node_count = support_band_counts[SUPPORT_BAND_WEAK_BUT_USABLE]
    usable_node_count = strong_node_count + good_node_count + weak_but_usable_node_count
    metrics = {
        "body_top1_threshold": threshold,
        "usable_support_threshold": USABLE_SUPPORT_THRESHOLD,
        "good_support_threshold": GOOD_SUPPORT_THRESHOLD,
        "strong_support_threshold": STRONG_SUPPORT_THRESHOLD,
        "candidate_node_count": candidate_node_count,
        "kept_node_count": kept_node_count,
        "pruned_node_count": len(pruned_nodes),
        "body_support_pass_ratio": _ratio(kept_node_count, candidate_node_count),
        "usable_support_ratio": _ratio(usable_node_count, candidate_node_count),
        "strong_support_ratio": _ratio(strong_node_count, candidate_node_count),
        "good_or_strong_support_ratio": _ratio(
            strong_node_count + good_node_count,
            candidate_node_count,
        ),
        "strong_node_count": strong_node_count,
        "good_node_count": good_node_count,
        "weak_but_usable_node_count": weak_but_usable_node_count,
        "unsupported_node_count": support_band_counts[SUPPORT_BAND_UNSUPPORTED],
        "support_band_counts": support_band_counts,
        "pruned_nodes": pruned_nodes,
    }
```

- [ ] **Step 3: Run tests and verify GREEN**

Run:

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_kg_body_grounding.py -q
```

Expected:

- PASS.

- [ ] **Step 4: Commit pruning metrics change**

Run:

```bash
git add ../backend/app/services/kg_body_grounding.py ../backend/tests/test_kg_body_grounding.py
git commit -m "调整KG正文支撑阈值指标"
```

If executing from repository root instead of `frontend/`, use paths without `../`.

## Task 3: CLI Defaults And Generation Strategy Tests

**Files:**

- Modify: `../backend/tests/test_generate_kg.py`
- Later modify: `../backend/tools/generate_knowledge_graph.py`

- [ ] **Step 1: Extend test imports**

In `../backend/tests/test_generate_kg.py`, update the import from `tools.generate_knowledge_graph` to include the new helpers:

```python
from tools.generate_knowledge_graph import (
    build_arg_parser,
    build_import_result,
    load_grounding_matches,
    load_kg_json,
    prune_kg_with_grounding_file,
    route_a_generation_strategy_for_threshold,
    validate_and_clean_kg,
)
```

Keep the file's existing aliases/imports intact if it already imports the module separately as `generate_kg_module`.

- [ ] **Step 2: Add failing parser default test**

Add this test near the grounding tests:

```python
def test_build_arg_parser_defaults_grounding_threshold_to_usable_060() -> None:
    parser = build_arg_parser()

    args = parser.parse_args(
        [
            "--course-id",
            "course-1",
            "--kg-json",
            "/tmp/kg.json",
            "--grounding-file",
            "/tmp/grounding.json",
        ]
    )

    assert args.grounding_threshold == 0.60
```

- [ ] **Step 3: Add failing generation strategy selection test**

Add this test after the parser default test:

```python
def test_route_a_generation_strategy_uses_usable_name_only_for_default_threshold() -> None:
    assert route_a_generation_strategy_for_threshold(0.60) == "route_a_prune_usable_060"
    assert route_a_generation_strategy_for_threshold(0.6000000001) == "route_a_prune_usable_060"
    assert route_a_generation_strategy_for_threshold(0.70) == "route_a_prune_unsupported"
```

- [ ] **Step 4: Add failing default pruning behavior test**

Add this test after `test_prune_kg_with_grounding_file_keeps_supported_nodes_and_metrics`:

```python
def test_prune_kg_with_grounding_file_defaults_to_usable_threshold(tmp_path: Path) -> None:
    nodes = [
        {"id": "node_1", "name": "变量", "chapter": "第一章"},
        {"id": "node_2", "name": "指针", "chapter": "第二章"},
        {"id": "node_3", "name": "数组", "chapter": "第三章"},
        {"id": "node_4", "name": "结构体", "chapter": "第四章"},
    ]
    edges = [
        {"from": "node_1", "to": "node_2"},
        {"from": "node_2", "to": "node_3"},
        {"from": "node_3", "to": "node_4"},
    ]
    grounding_file = tmp_path / "grounding.json"
    grounding_file.write_text(
        """
        {
          "course_id": "course-1",
          "threshold": 0.7,
          "results": [
            {
              "node_id": "node_1",
              "body_top1_score": 0.91,
              "chunk_id": "chunk-a",
              "preview": "变量用于保存程序运行中的数据。"
            },
            {
              "node_id": "node_2",
              "body_top1_score": 0.62,
              "chunk_id": "chunk-b",
              "preview": "指针保存地址。"
            },
            {
              "node_id": "node_3",
              "body_top1_score": 0.59,
              "chunk_id": "chunk-c",
              "preview": "数组候选分数不足。"
            },
            {
              "node_id": "node_4",
              "body_top1_score": null,
              "chunk_id": null,
              "preview": ""
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    kept_nodes, kept_edges, metrics = prune_kg_with_grounding_file(
        nodes,
        edges,
        grounding_file,
    )

    assert kept_nodes == nodes[:2]
    assert kept_edges == [{"from": "node_1", "to": "node_2"}]
    assert metrics["body_top1_threshold"] == 0.60
    assert metrics["candidate_node_count"] == 4
    assert metrics["kept_node_count"] == 2
    assert metrics["pruned_node_count"] == 2
    assert metrics["body_support_pass_ratio"] == 0.5
    assert metrics["usable_support_ratio"] == 0.5
    assert metrics["strong_support_ratio"] == 0.25
    assert metrics["good_or_strong_support_ratio"] == 0.25
    assert metrics["support_band_counts"] == {
        "strong": 1,
        "good": 0,
        "weak_but_usable": 1,
        "unsupported": 2,
    }
```

- [ ] **Step 5: Update existing explicit-threshold CLI pruning assertions**

In `test_prune_kg_with_grounding_file_keeps_supported_nodes_and_metrics`, keep `threshold=0.70` and add these assertions after the existing ratio assertion:

```python
    assert metrics["usable_support_ratio"] == pytest.approx(1.0)
    assert metrics["strong_support_ratio"] == pytest.approx(2 / 3)
    assert metrics["good_or_strong_support_ratio"] == pytest.approx(1.0)
    assert metrics["support_band_counts"] == {
        "strong": 2,
        "good": 1,
        "weak_but_usable": 0,
        "unsupported": 0,
    }
```

Why `usable_support_ratio == 1.0`: the explicit strict pruning threshold keeps only nodes `>=0.70`, but all three candidates still have fixed usable support `>=0.60`.

- [ ] **Step 6: Run tests and verify RED**

Run:

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_generate_kg.py -q
```

Expected:

- FAIL because `build_arg_parser` and `route_a_generation_strategy_for_threshold` do not exist, or because the CLI default is still `0.70`.

## Task 4: CLI Defaults And Strategy Implementation

**Files:**

- Modify: `../backend/tools/generate_knowledge_graph.py`
- Test: `../backend/tests/test_generate_kg.py`

- [ ] **Step 1: Update imports**

In `../backend/tools/generate_knowledge_graph.py`, add `math` and import `USABLE_SUPPORT_THRESHOLD`:

```python
import math
```

Update the existing `app.services.kg_body_grounding` import to:

```python
from app.services.kg_body_grounding import (
    GroundingMatch,
    USABLE_SUPPORT_THRESHOLD,
    filter_supported_knowledge_graph,
)
```

- [ ] **Step 2: Change pruning wrapper default**

Update the `prune_kg_with_grounding_file()` signature:

```python
def prune_kg_with_grounding_file(
    nodes: list[dict],
    edges: list[dict],
    grounding_file: Path,
    *,
    threshold: float = USABLE_SUPPORT_THRESHOLD,
) -> tuple[list[dict], list[dict], dict]:
```

- [ ] **Step 3: Add strategy helper**

Add this helper above `main_async()`:

```python
def route_a_generation_strategy_for_threshold(threshold: float) -> str:
    if math.isclose(
        threshold,
        USABLE_SUPPORT_THRESHOLD,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        return "route_a_prune_usable_060"
    return "route_a_prune_unsupported"
```

- [ ] **Step 4: Extract parser construction**

Move the parser construction currently inside `main_async()` into this new helper above `main_async()`:

```python
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CourseKnowledgeGraph 智能生成与导入运维工具")
    parser.add_argument("--course-id", required=True, help="课程 ID")
    parser.add_argument("--auto", action="store_true", help="跳过用户命令行交互，直接落库")
    parser.add_argument("--grounding-file", type=Path, help="Agent kg_body_grounding JSON output for Route A pruning")
    parser.add_argument(
        "--grounding-threshold",
        type=float,
        default=USABLE_SUPPORT_THRESHOLD,
        help="Route A body grounding score threshold",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", "-f", help="课程大纲文本文档路径")
    src.add_argument("--outline", "-o", help="直接传入课程大纲文本")
    src.add_argument("--kg-json", type=Path, help="直接读取现有 KG JSON，跳过 LLM 生成")
    return parser
```

At the top of `main_async()`, replace the inlined parser construction with:

```python
    parser = build_arg_parser()
    args = parser.parse_args()
```

- [ ] **Step 5: Use the strategy helper**

Inside `main_async()`, replace:

```python
        generation_strategy = "route_a_prune_unsupported"
```

with:

```python
        generation_strategy = route_a_generation_strategy_for_threshold(args.grounding_threshold)
```

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_generate_kg.py -q
```

Expected:

- PASS.

- [ ] **Step 7: Commit CLI default and strategy change**

Run:

```bash
git add ../backend/tools/generate_knowledge_graph.py ../backend/tests/test_generate_kg.py
git commit -m "调整Route A生成阈值默认策略"
```

If executing from repository root instead of `frontend/`, use paths without `../`.

## Task 5: Combined Regression Verification

**Files:**

- No production file changes expected.
- Tests: `../backend/tests/test_kg_body_grounding.py`, `../backend/tests/test_generate_kg.py`, `../backend/tests/test_kg_cli_versioning.py`, `../backend/tests/test_course_knowledge_graph_versions.py`

- [ ] **Step 1: Run focused Backend tests**

Run:

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q
```

Expected:

- PASS.

- [ ] **Step 2: Run MySQL versioning regression**

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected:

- PASS or SKIP only if MySQL is unavailable.
- If it fails because the MySQL service or test database is missing, record that as an environment blocker and do not replace it with SQLite.

- [ ] **Step 3: Inspect changed files**

Run:

```bash
git status --short
git diff -- ../backend/app/services/kg_body_grounding.py ../backend/tools/generate_knowledge_graph.py ../backend/tests/test_kg_body_grounding.py ../backend/tests/test_generate_kg.py
```

Expected:

- Only intended Backend files changed in this batch.
- No OpenAPI, Client API docs, Agent grounding output shape, `.env`, storage, Qdrant, MySQL volume, or upload files changed.

## Task 6: Real C-Language Route A Version Verification

**Files:**

- No code changes expected.
- May write a new active KG version to MySQL dev DB.

- [ ] **Step 1: Confirm sample files exist**

Run:

```bash
test -f /tmp/kg-resource-probe/c-language-active-kg-v1.json
test -f /tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json
```

Expected:

- Both commands exit `0`.
- If either file is missing, skip this task and record that real sample verification was not rerun in this session.

- [ ] **Step 2: Generate the new active Route A version**

Run:

```bash
cd ../backend
set -a
. ../agent_service/.env
set +a
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python tools/generate_knowledge_graph.py \
  --course-id 6c698badb60a4809 \
  --kg-json /tmp/kg-resource-probe/c-language-active-kg-v1.json \
  --grounding-file /tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json \
  --grounding-threshold 0.60 \
  --auto
```

Expected:

- Command succeeds.
- Printed result has a new `graph_id`, `source_type=route_a_body_grounded`, and `generation_strategy=route_a_prune_usable_060`.
- Printed node count is `108`.
- Printed edge count is materially higher than the old Route A `2` edges.

- [ ] **Step 3: Verify the latest active graph metrics**

Run this read-only check:

```bash
cd ../backend
set -a
. ../agent_service/.env
set +a
../.venv/bin/python - <<'PY'
import asyncio
import json
from sqlalchemy import select
from app.db.session import async_session_factory, engine
from app.models.others import CourseKnowledgeGraph

COURSE_ID = "6c698badb60a4809"

async def main():
    async with async_session_factory() as db:
        result = await db.execute(
            select(CourseKnowledgeGraph)
            .where(
                CourseKnowledgeGraph.course_id == COURSE_ID,
                CourseKnowledgeGraph.is_active.is_(True),
            )
            .order_by(CourseKnowledgeGraph.version.desc())
            .limit(1)
        )
        graph = result.scalar_one()
        print(
            json.dumps(
                {
                    "graph_id": graph.id,
                    "version": graph.version,
                    "source_type": graph.source_type,
                    "generation_strategy": graph.generation_strategy,
                    "node_count": len(graph.nodes or []),
                    "edge_count": len(graph.edges or []),
                    "metrics": graph.metrics,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    await engine.dispose()

asyncio.run(main())
PY
```

Expected:

```json
{
  "source_type": "route_a_body_grounded",
  "generation_strategy": "route_a_prune_usable_060",
  "node_count": 108,
  "metrics": {
    "body_top1_threshold": 0.6,
    "usable_support_threshold": 0.6,
    "good_support_threshold": 0.65,
    "strong_support_threshold": 0.7,
    "candidate_node_count": 116,
    "kept_node_count": 108,
    "pruned_node_count": 8,
    "body_support_pass_ratio": 0.9310344827586207,
    "usable_support_ratio": 0.9310344827586207,
    "strong_support_ratio": 0.49137931034482757,
    "good_or_strong_support_ratio": 0.7844827586206896,
    "strong_node_count": 57,
    "good_node_count": 34,
    "weak_but_usable_node_count": 17,
    "unsupported_node_count": 8,
    "support_band_counts": {
      "strong": 57,
      "good": 34,
      "weak_but_usable": 17,
      "unsupported": 8
    }
  }
}
```

Only compare fields relevant to this task. `graph_id`, `version`, `edge_count`, and `grounding_source_file` are environment-dependent.

## Task 7: Progress Docs

**Files:**

- Modify: `../backend/WORKFLOW.md`
- Modify: `WORKFLOW.md`
- Modify: `docs/feature-ledger.md`

- [ ] **Step 1: Update Backend workflow**

Add a new item near the top of `../backend/WORKFLOW.md` recent verification section:

```markdown
- 2026-06-11：Route A 可用正文支撑阈值实现：
  - Backend Route A 裁剪默认阈值从 `0.70` 改为 `0.60`；显式传入其他阈值时仍按传入阈值裁剪，`body_support_pass_ratio` 保持兼容语义。
  - `filter_supported_knowledge_graph()` 新增固定 `0.60/0.65/0.70` 支撑分档 metrics；`strong/good/weak_but_usable/unsupported` count 均按全部 candidate nodes 统计。
  - CLI `--grounding-threshold` 默认改为 `0.60`，默认 Route A 版本写入 `generation_strategy=route_a_prune_usable_060`；显式非 `0.60` 阈值仍写 `route_a_prune_unsupported`。
  - 已知后续风险：`metrics.pruned_nodes` 仍保留完整 detail 列表，当前 C 语言样本只裁 8 个节点可接受；未来更大图需要考虑限长或外部诊断文件。
  - 验证：`../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q` 通过；MySQL versioning 回归和真实样本生成结果见本轮记录。
```

If real sample or MySQL regression was not run, replace the final bullet with the actual commands and blocker reason.

- [ ] **Step 2: Update frontend workflow**

In `WORKFLOW.md`, add a matching recent verification item summarizing the project-level impact:

```markdown
- 2026-06-11：Route A 可用正文支撑阈值实现计划/落地：
  - Route A active KG 裁剪默认线从强支撑 `0.70` 调整为可用支撑 `0.60`，并保留 `strong/good/weak_but_usable/unsupported` 分档 metrics。
  - `body_support_pass_ratio` 继续按传入阈值计算；`usable_support_ratio` 固定按 `0.60` 计算，避免后续 ready gate 把 weak support 当作 strong support。
  - `pruned_nodes` 详细列表暂保留，未来大图需要做限长或外部诊断产物。
  - 验证：填写实际运行的 Backend 测试、MySQL 回归、真实 C 语言样本结果。
```

- [ ] **Step 3: Update feature ledger next-step queue**

In `docs/feature-ledger.md`, update the KG next-step queue:

- If real sample generation passed, mark "正文驱动 KG 生成策略修正" as Route A usable-threshold version generated and make the next step "KG-Resource 对齐探针".
- If only code/tests passed and real sample was not run, keep the item active and state the remaining blocker is real MySQL sample generation.

Use this text if real sample passed:

```markdown
1. **KG-Resource 对齐探针复验**
   Route A 可用支撑阈值版本已按 `>=0.60` 生成，metrics 保留 `strong/good/weak_but_usable/unsupported` 分布。下一步跑 KG-Resource 对齐探针，确认 LearningPath 节点到资源的命名和章节匹配是否改善。
```

Use this text if real sample was not run:

```markdown
1. **Route A 可用支撑阈值真实样本生成**
   代码层已将 Route A 默认裁剪线调整为 `0.60` 并补充分档 metrics；下一步必须用 `/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json` 在 MySQL 开发库生成新 active KG，核验 `108/116` 节点和 `57/34/17/8` 分档。
```

- [ ] **Step 4: Commit progress docs**

Run:

```bash
git add ../backend/WORKFLOW.md WORKFLOW.md docs/feature-ledger.md
git commit -m "记录Route A可用阈值进展"
```

If executing from repository root instead of `frontend/`, adjust paths accordingly.

## Task 8: Final Verification And Completion Review

**Files:**

- No new changes expected.

- [ ] **Step 1: Run final focused verification**

Run:

```bash
cd ../backend
../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q
```

Expected:

- PASS.

- [ ] **Step 2: Run final git review**

Run:

```bash
git status --short
git log --oneline -5
```

Expected:

- No unintended `.env`, storage, Qdrant, MySQL volume, upload, build, cache, or `node_modules` changes staged or committed.
- Commits include the three planned Chinese messages:
  - `调整KG正文支撑阈值指标`
  - `调整Route A生成阈值默认策略`
  - `记录Route A可用阈值进展`

- [ ] **Step 3: Completion summary**

Final response must include:

- 当前完成 / 实现状态.
- 修改文件.
- 测试结果 with exact commands and pass/fail/skip.
- OpenAPI/契约是否漂移: expected "无漂移，未修改 Client API / Agent API / OpenAPI".
- git commit 信息.
- 剩余风险, including unbounded `pruned_nodes` detail list and whether real sample generation was run.
- 下一步建议: KG-Resource 对齐探针 if real sample passed; otherwise run the real MySQL sample generation.

## Self-Review

Spec coverage:

- Default Route A threshold `0.60`: Task 3 and Task 4.
- `filter_supported_knowledge_graph()` band metrics: Task 1 and Task 2.
- Explicit `0.70` compatibility: Task 1 and Task 3.
- `body_support_pass_ratio` vs fixed `usable_support_ratio`: Task 1 explicit-threshold test.
- Counts over all candidates: Task 1 explicit-threshold test and metrics implementation.
- CLI `generation_strategy=route_a_prune_usable_060`: Task 3 and Task 4.
- Real sample verification: Task 6.
- Docs/progress updates and deferred `pruned_nodes` risk: Task 7.
- No OpenAPI/Client API drift: Scope, Task 5, Task 8.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified "write tests later" placeholders.

Type/name consistency:

- New helper names are consistently `build_arg_parser()` and `route_a_generation_strategy_for_threshold()`.
- Metrics keys match the spec and user clarifications.
