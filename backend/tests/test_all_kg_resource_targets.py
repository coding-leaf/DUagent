from app.services import kg_resource_targets


def _node(index: int) -> dict:
    return {
        "id": f"node-{index}",
        "name": f"知识点 {index}",
        "chapter": f"第 {index % 3 + 1} 章",
        "support_band": "strong",
        "body_top1_score": 0.8,
    }


def test_select_valid_targets_keeps_every_supported_node_without_business_limit():
    select_targets = getattr(
        kg_resource_targets,
        "select_valid_resource_targets",
        None,
    )
    assert callable(select_targets), "resource generation needs an unlimited selector"

    result = select_targets([_node(index) for index in range(14)])

    assert len(result["targets"]) == 14
    assert result["skipped"] == []


def test_select_valid_targets_reports_invalid_duplicate_and_unsupported_nodes():
    select_targets = getattr(
        kg_resource_targets,
        "select_valid_resource_targets",
        None,
    )
    assert callable(select_targets), "resource generation needs an unlimited selector"
    nodes = [
        _node(1),
        {**_node(2), "name": "知识点 1", "chapter": "第 2 章"},
        {**_node(3), "support_band": "unsupported"},
        {"id": "missing", "name": "", "chapter": "第 1 章"},
    ]

    result = select_targets(nodes)

    assert len(result["targets"]) == 1
    assert {item["reason"] for item in result["skipped"]} == {
        "duplicate_chapter_name",
        "unsupported",
        "missing_required_fields",
    }
