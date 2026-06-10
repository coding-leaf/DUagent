from app.services.kg_body_grounding import (
    GroundingMatch,
    filter_supported_knowledge_graph,
    is_toc_like_chunk,
)


def test_is_toc_like_chunk_detects_markers_and_explanatory_body() -> None:
    assert is_toc_like_chunk("")
    assert is_toc_like_chunk("  \n\t")
    assert is_toc_like_chunk("目录\n第一章 C 语言概述 ........ 1")
    assert is_toc_like_chunk("Table of Contents\n1. Introduction ........ 1")
    assert is_toc_like_chunk("CONTENTS\nChapter 1 Basics 3")
    assert is_toc_like_chunk(
        "\n".join(
            [
                "第 1 章 计算机基础 1",
                "1.1 程序设计入门 3",
                "Chapter 2 Pointers 15",
                "2.3 Arrays ........ 28",
            ]
        )
    )

    explanatory_body = (
        "C 语言中的指针保存的是变量的内存地址。"
        "通过指针可以间接访问对象，并在函数调用时共享同一份数据。"
    )
    assert not is_toc_like_chunk(explanatory_body)


def test_is_toc_like_chunk_does_not_match_body_marker_words_or_trailing_numbers() -> None:
    body_with_contents = (
        "The contents of this section explain how arrays store adjacent elements. "
        "It is body prose, not a table of contents."
    )
    body_with_catalog_word = (
        "本节会说明目录变量如何参与文件路径解析，"
        "这里的目录是正文术语，不是章节索引。"
    )
    body_ending_with_numbers = "\n".join(
        [
            "C99 introduced several language updates in 1999",
            "The example stores the value 42",
            "A pointer may reference element 10",
        ]
    )

    assert not is_toc_like_chunk(body_with_contents)
    assert not is_toc_like_chunk(body_with_catalog_word)
    assert not is_toc_like_chunk(body_ending_with_numbers)


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


def test_filter_supported_knowledge_graph_handles_zero_candidate_nodes() -> None:
    filtered_nodes, filtered_edges, metrics = filter_supported_knowledge_graph(
        [],
        [{"from": "missing-a", "to": "missing-b"}],
        [
            GroundingMatch(
                node_id="missing-a",
                score=0.95,
                chunk_id="chunk-x",
                content_preview="unused",
            )
        ],
    )

    assert filtered_nodes == []
    assert filtered_edges == []
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


def test_filter_supported_knowledge_graph_uses_highest_duplicate_match() -> None:
    nodes = [{"id": "node-1", "name": "函数", "chapter": "第五章"}]
    matches = [
        GroundingMatch(
            node_id="node-1",
            score=0.91,
            chunk_id="chunk-high",
            content_preview="函数用于组织可复用逻辑。",
        ),
        GroundingMatch(
            node_id="node-1",
            score=0.42,
            chunk_id="chunk-low",
            content_preview="低分重复记录不应覆盖高分记录。",
        ),
    ]

    filtered_nodes, _, metrics = filter_supported_knowledge_graph(nodes, [], matches)

    assert filtered_nodes == nodes
    assert metrics["kept_node_count"] == 1
    assert metrics["pruned_nodes"] == []


def test_filter_supported_knowledge_graph_returns_shallow_copies() -> None:
    nodes = [{"id": "node-1", "name": "循环", "chapter": "第三章"}]
    edges = [{"from": "node-1", "to": "node-1", "type": "self"}]
    matches = [
        GroundingMatch(
            node_id="node-1",
            score=0.80,
            chunk_id="chunk-a",
            content_preview="循环结构用于重复执行语句。",
        )
    ]

    filtered_nodes, filtered_edges, _ = filter_supported_knowledge_graph(
        nodes,
        edges,
        matches,
    )
    filtered_nodes[0]["name"] = "mutated"
    filtered_edges[0]["type"] = "mutated"

    assert nodes[0]["name"] == "循环"
    assert edges[0]["type"] == "self"
