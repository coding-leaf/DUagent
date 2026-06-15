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
