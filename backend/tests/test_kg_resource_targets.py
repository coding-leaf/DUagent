from app.services.kg_resource_targets import select_valid_resource_targets


def _node(node_id, name, chapter, band=None, score=None):
    node = {"id": node_id, "name": name, "chapter": chapter}
    if band is not None:
        node["support_band"] = band
    if score is not None:
        node["body_top1_score"] = score
    return node


def test_select_valid_targets_keeps_all_supported_bands():
    nodes = [
        _node(f"s{i}", f"Strong {i}", "第一章", "strong", 0.90 - i * 0.01)
        for i in range(12)
    ] + [
        _node("g1", "Good Other Chapter", "第二章", "good", 0.68),
    ]

    result = select_valid_resource_targets(nodes)

    assert len(result["targets"]) == 13
    assert [item["support_band"] for item in result["targets"]] == ["strong"] * 12 + ["good"]
    assert "Good Other Chapter" in [item["node_name"] for item in result["targets"]]
    assert result["selection_degraded"] is False


def test_select_valid_targets_preserves_kg_order():
    nodes = [
        _node("a1", "A1", "第一章", "strong", 0.91),
        _node("a2", "A2", "第一章", "strong", 0.90),
        _node("b1", "B1", "第二章", "strong", 0.89),
        _node("b2", "B2", "第二章", "strong", 0.88),
        _node("c1", "C1", "第三章", "strong", 0.87),
    ]

    result = select_valid_resource_targets(nodes)

    assert [item["chapter"] for item in result["targets"]] == [
        "第一章",
        "第一章",
        "第二章",
        "第二章",
        "第三章",
    ]


def test_select_valid_targets_drops_unsupported_and_deduplicates_chapter_name():
    nodes = [
        _node("n1", "数组", "第三章", "good", 0.66),
        _node("n1-dup", "数组", "第三章", "strong", 0.82),
        _node("bad", "目录", "附录", "unsupported", 0.40),
        _node("missing-name", "", "第三章", "strong", 0.80),
        _node("missing-chapter", "函数", "", "strong", 0.80),
    ]

    result = select_valid_resource_targets(nodes)

    assert result["targets"] == [
        {
            "node_id": "n1-dup",
            "node_name": "数组",
            "chapter": "第三章",
            "support_band": "strong",
            "body_top1_score": 0.82,
        }
    ]


def test_select_valid_targets_degrades_when_nodes_have_no_support_metadata():
    nodes = [
        {"id": "n1", "name": "变量", "chapter": "第一章"},
        {"id": "n2", "name": "指针", "chapter": "第二章"},
        {"id": "n3", "name": "数组", "chapter": "第一章"},
    ]

    result = select_valid_resource_targets(nodes)

    assert result["targets"] == [
        {
            "node_id": "n1",
            "node_name": "变量",
            "chapter": "第一章",
            "support_band": "unknown",
            "body_top1_score": None,
        },
        {
            "node_id": "n2",
            "node_name": "指针",
            "chapter": "第二章",
            "support_band": "unknown",
            "body_top1_score": None,
        },
        {
            "node_id": "n3",
            "node_name": "数组",
            "chapter": "第一章",
            "support_band": "unknown",
            "body_top1_score": None,
        },
    ]
    assert result["selection_degraded"] is True
    assert result["degraded_reason"] == "node_support_metadata_missing"
