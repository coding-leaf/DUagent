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


def test_filter_supported_knowledge_graph_prunes_nodes_edges_and_metrics() -> None:
    nodes = [
        {"id": "node-1", "name": "变量", "chapter": "第一章"},
        {"id": "node-2", "name": "指针", "chapter": "第二章"},
        {"id": "node-3", "name": "数组", "chapter": "第三章"},
        {"id": "node-4", "name": "结构体", "chapter": "第四章"},
    ]
    edges = [
        {"from": "node-1", "to": "node-2"},
        {"from": "node-2", "to": "node-3"},
        {"from": "node-2", "to": "node-4"},
        {"from": "node-3", "to": "node-4"},
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
            score=0.69,
            chunk_id="chunk-c",
            content_preview="数组是一组连续元素。",
        ),
    ]

    filtered_nodes, filtered_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        edges,
        matches,
    )

    assert filtered_nodes == nodes[:2]
    assert filtered_edges == [{"from": "node-1", "to": "node-2"}]
    assert metrics == {
        "body_top1_threshold": 0.70,
        "candidate_node_count": 4,
        "kept_node_count": 2,
        "pruned_node_count": 2,
        "body_support_pass_ratio": 0.5,
        "pruned_nodes": [
            {
                "node_id": "node-3",
                "node_name": "数组",
                "chapter": "第三章",
                "body_top1_score": 0.69,
                "chunk_id": "chunk-c",
                "content_preview": "数组是一组连续元素。",
            },
            {
                "node_id": "node-4",
                "node_name": "结构体",
                "chapter": "第四章",
                "body_top1_score": None,
                "chunk_id": None,
                "content_preview": "",
            },
        ],
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
        "body_top1_threshold": 0.70,
        "candidate_node_count": 0,
        "kept_node_count": 0,
        "pruned_node_count": 0,
        "body_support_pass_ratio": 0.0,
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
