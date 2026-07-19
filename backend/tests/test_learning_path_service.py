from app.services.learning_path_service import (
    apply_progress_to_nodes,
    build_current_position_from_nodes,
    map_assessment_to_status,
    topo_sort_kg_nodes,
)


def test_topo_sort_preserves_prerequisite_order():
    nodes = [
        {"id": "b", "name": "B"},
        {"id": "a", "name": "A"},
        {"id": "c", "name": "C"},
    ]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]

    result = topo_sort_kg_nodes(nodes, edges)

    assert [node["id"] for node in result] == ["a", "b", "c"]


def test_apply_progress_to_nodes_preserves_unknown_nodes():
    nodes = [{"id": "n1", "name": "Node 1", "status": "pending", "mastery": 10, "reason": "keep"}]

    result = apply_progress_to_nodes(nodes, {})

    assert result == [{"id": "n1", "name": "Node 1", "status": "pending", "mastery": 10, "reason": "keep"}]
    assert result is not nodes


def test_apply_progress_to_nodes_maps_status_and_mastery():
    nodes = [{"id": "n1", "name": "Node 1", "status": "pending", "mastery": 0}]
    progress = {"n1": {"assessment_state": "mastered", "mastery_score": 93.5}}

    result = apply_progress_to_nodes(nodes, progress)

    assert result[0]["status"] == "completed"
    assert result[0]["mastery"] == 93.5


def test_status_mapping_defaults_to_pending():
    assert map_assessment_to_status("unknown") == "pending"


def test_current_position_uses_first_non_pending_node():
    nodes = [
        {"id": "n1", "name": "Node 1", "status": "pending"},
        {"id": "n2", "name": "Node 2", "status": "recommended"},
    ]

    assert build_current_position_from_nodes(nodes) == {"node_id": "n2", "node_name": "Node 2"}
