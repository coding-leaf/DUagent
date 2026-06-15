"""Unit tests for realtime node status mapping in learning_path.py.

Run: python -m pytest tests/test_learning_path_realtime.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_lp_realtime.db",
)

import pytest
from app.api.v1.learning_path import _map_assessment_to_status


class TestMapAssessmentToStatus:
    def test_mastered_maps_to_completed(self):
        assert _map_assessment_to_status("mastered") == "completed"

    def test_learning_maps_to_in_progress(self):
        assert _map_assessment_to_status("learning") == "in_progress"

    def test_weak_maps_to_recommended(self):
        assert _map_assessment_to_status("weak") == "recommended"

    def test_pending_practice_maps_to_pending(self):
        assert _map_assessment_to_status("pending_practice") == "pending"

    def test_unstarted_maps_to_pending(self):
        assert _map_assessment_to_status("unstarted") == "pending"

    def test_unknown_state_maps_to_pending(self):
        assert _map_assessment_to_status("something_else") == "pending"


from app.api.v1.learning_path import _apply_progress_to_nodes, _build_current_position_from_nodes


class TestApplyProgressToNodes:
    def test_merges_status_from_progress(self):
        nodes = [
            {"id": "n1", "name": "A", "order": 1, "status": "recommended", "mastery": 0},
            {"id": "n2", "name": "B", "order": 2, "status": "recommended", "mastery": 0},
        ]
        progress = {
            "n1": {"assessment_state": "mastered", "mastery_score": 92.0},
            "n2": {"assessment_state": "learning", "mastery_score": 45.0},
        }
        result = _apply_progress_to_nodes(nodes, progress)
        assert result[0]["status"] == "completed"
        assert result[0]["mastery"] == 92.0
        assert result[1]["status"] == "in_progress"
        assert result[1]["mastery"] == 45.0

    def test_preserves_other_fields(self):
        nodes = [{"id": "n1", "name": "A", "order": 3, "status": "pending", "mastery": 0, "reason": "原因"}]
        progress = {"n1": {"assessment_state": "mastered", "mastery_score": 85.0}}
        result = _apply_progress_to_nodes(nodes, progress)
        assert result[0]["order"] == 3
        assert result[0]["reason"] == "原因"

    def test_node_not_in_progress_keeps_original_status(self):
        nodes = [{"id": "n99", "name": "Z", "order": 1, "status": "pending", "mastery": 0}]
        result = _apply_progress_to_nodes(nodes, {})
        assert result[0]["status"] == "pending"

    def test_mastery_score_none_keeps_original_mastery(self):
        nodes = [{"id": "n1", "name": "A", "order": 1, "status": "pending", "mastery": 10}]
        progress = {"n1": {"assessment_state": "unstarted", "mastery_score": None}}
        result = _apply_progress_to_nodes(nodes, progress)
        assert result[0]["mastery"] == 10


class TestBuildCurrentPositionFromNodes:
    def test_returns_first_non_pending_node(self):
        nodes = [
            {"id": "n1", "name": "A", "status": "pending"},
            {"id": "n2", "name": "B", "status": "in_progress"},
            {"id": "n3", "name": "C", "status": "completed"},
        ]
        cp = _build_current_position_from_nodes(nodes)
        assert cp == {"node_id": "n2", "node_name": "B"}

    def test_all_pending_returns_first_node(self):
        nodes = [
            {"id": "n1", "name": "A", "status": "pending"},
            {"id": "n2", "name": "B", "status": "pending"},
        ]
        cp = _build_current_position_from_nodes(nodes)
        assert cp == {"node_id": "n1", "node_name": "A"}

    def test_empty_nodes_returns_none(self):
        assert _build_current_position_from_nodes([]) is None
