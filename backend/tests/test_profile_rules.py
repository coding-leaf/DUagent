import pytest
from datetime import datetime, timezone, timedelta
from app.services.profile_rules import (
    compute_modal_preference,
    compute_knowledge_progress,
    compute_learning_habits,
    compute_discipline_badge,
    compute_streak_days,
    count_recent_practice_events,
)

def test_compute_modal_preference():
    activities = [
        ("mindmap", 2),
        ("lesson", 4),
        ("example", 2),
    ]
    prefs = compute_modal_preference(activities, ai_interaction_count=3)
    assert prefs["video_animation"] == 75  # 3/4 * 100
    assert prefs["chart_logic"] == 50      # 2/4 * 100
    assert prefs["text_analysis"] == 100   # 4/4 * 100
    assert prefs["code_practice"] == 50    # 2/4 * 100
    assert prefs["formula_derivation"] == 0

def test_compute_modal_preference_3_tuples_and_new_types():
    activities = [
        ("personal_lesson", "resource_study", 2),
        ("practice", "resource_study", 1),
        (None, "node_practice_submit", 4),
    ]
    prefs = compute_modal_preference(activities)
    assert prefs["text_analysis"] == 50       # 2/4 * 100
    assert prefs["formula_derivation"] == 25  # 1/4 * 100
    assert prefs["code_practice"] == 100      # 4/4 * 100

def test_compute_modal_preference_empty():
    prefs = compute_modal_preference([])
    assert all(v == 0 for v in prefs.values())

def test_compute_knowledge_progress():
    node_progress_rows = [
        {"node_id": "n1", "node_name": "Node 1", "assessment_state": "mastered", "mastery_score": 90, "attempt_count": 1, "study_duration_seconds": 600},
        {"node_id": "n2", "node_name": "Node 2", "assessment_state": "weak", "mastery_score": 40, "attempt_count": 2, "study_duration_seconds": 300},
        {"node_id": "n3", "node_name": "Node 3", "assessment_state": "learning", "mastery_score": 0, "attempt_count": 0, "study_duration_seconds": 100},
        {"node_id": "n4", "node_name": "Node 4", "assessment_state": "pending_practice", "mastery_score": None, "attempt_count": 0, "study_duration_seconds": 0},
        {"node_id": "n5", "node_name": "Node 5", "assessment_state": "unstarted", "mastery_score": None, "attempt_count": 0, "study_duration_seconds": 0},
    ]
    coords, weak_nodes, summary = compute_knowledge_progress(node_progress_rows)
    
    assert len(coords) == 5
    assert coords[0]["evidence"] == "quiz"
    assert coords[2]["evidence"] == "activity"
    assert coords[3]["evidence"] == "none"

    assert len(weak_nodes) == 1
    assert weak_nodes[0]["name"] == "Node 2"
    assert weak_nodes[0]["severity"] == "high"

    assert summary["total_nodes"] == 5
    assert summary["mastered_nodes"] == 1
    assert summary["learning_nodes"] == 1
    assert summary["weak_nodes"] == 1
    assert summary["pending_nodes"] == 1
    assert summary["unstarted_nodes"] == 1
    assert summary["practiced_nodes"] == 3
    assert summary["mastery_rate"] == 20

def test_compute_streak_days_counts_consecutive_dates_through_today():
    now = datetime(2023, 1, 15, 12, 0, tzinfo=timezone.utc)
    activity_dates = [
        now,
        now - timedelta(days=1),
        now - timedelta(days=2),
        now - timedelta(days=4),
    ]

    assert compute_streak_days(activity_dates, now) == 3

def test_compute_streak_days_allows_yesterday_as_active_streak_start():
    now = datetime(2023, 1, 15, 12, 0, tzinfo=timezone.utc)
    activity_dates = [
        now - timedelta(days=1),
        now - timedelta(days=2),
        now - timedelta(days=3),
    ]

    assert compute_streak_days(activity_dates, now) == 3

def test_count_recent_practice_events_filters_activity_type_and_window():
    now = datetime(2023, 1, 15, 12, 0, tzinfo=timezone.utc)
    rows = [
        ("node_practice_submit", now - timedelta(days=1)),
        ("node_practice_submit", now - timedelta(days=6, hours=23)),
        ("node_practice_submit", now - timedelta(days=8)),
        ("resource_study", now - timedelta(days=1)),
    ]

    assert count_recent_practice_events(rows, now, days=7) == 2

def test_compute_learning_habits():
    now = datetime(2023, 1, 15, 12, 0, tzinfo=timezone.utc)
    last_activity = now - timedelta(hours=10)
    
    habits, score = compute_learning_habits(
        last_activity_at=last_activity,
        study_duration_7d=3600,
        study_duration_30d=14400,
        active_days_7d=5,
        streak_days=3,
        practice_count_7d=2,
        total_events=20,
        total_nodes=10,
        now=now
    )
    
    assert habits["label"] in ["stable", "sprint", "casual"]
    assert "score" in habits
    assert habits["streak_days"] == 3
    assert habits["active_days_7d"] == 5

def test_compute_discipline_badge():
    badge = compute_discipline_badge(
        course_id="c1",
        weak_count=2,
        total_nodes=10,
        learning_habit_score=80.0,
        mastery_rate=60,
        streak_days=5
    )
    
    assert badge["subject"] == "c1"
    assert "level" in badge
    assert "score" in badge
    assert badge["streak_days"] == 5
    
    score = badge["score"]
    # (80 * 0.4) + (60 * 0.5) - ((2/10*100) * 0.1) = 32 + 30 - 2 = 60
    assert score == 60
    assert badge["level"] == "steady"
