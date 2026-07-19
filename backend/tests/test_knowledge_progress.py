import pytest
from datetime import datetime, timedelta

from app.services.knowledge_progress import evaluate_mastery_state, summarize_attempt_answers

def test_evaluate_mastery_state_with_no_questions_and_no_activity():
    # Empty state
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=None,
        question_count=0,
        attempt_count=0,
        latest_score=None,
        has_activity=False
    )
    assert assessment_state == "unstarted"
    assert status_text == "未开始"
    assert mastery_label == "无测评"

def test_evaluate_mastery_state_with_no_questions_but_has_activity():
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=None,
        question_count=0,
        attempt_count=0,
        latest_score=None,
        has_activity=True
    )
    assert assessment_state == "learning"
    assert status_text == "学习中"
    assert mastery_label == "无测评"

def test_evaluate_mastery_state_pending_practice():
    # Has questions, but no score yet
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=None,
        question_count=5,
        attempt_count=0,
        latest_score=None,
        has_activity=True
    )
    assert assessment_state == "pending_practice"
    assert status_text == "待练习"
    assert mastery_label == "待练习"

def test_evaluate_mastery_state_mastered():
    # score >= 80, attempt_count >= min_evidence (min(3, 5) = 3)
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=85.0,
        question_count=5,
        attempt_count=3,
        latest_score=85.0,
        has_activity=True
    )
    assert assessment_state == "mastered"
    assert status_text == "已掌握"
    assert mastery_label == "B"

def test_evaluate_mastery_state_mastered_few_questions():
    # score >= 80, attempt_count >= min_evidence (min(3, 2) = 2)
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=95.0,
        question_count=2,
        attempt_count=2,
        latest_score=95.0,
        has_activity=True
    )
    assert assessment_state == "mastered"
    assert status_text == "已掌握"
    assert mastery_label == "A"

def test_evaluate_mastery_state_high_score_not_enough_evidence():
    # score >= 80, but attempt_count < min_evidence (2 < 3)
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=95.0,
        question_count=5,
        attempt_count=2,
        latest_score=95.0,
        has_activity=True
    )
    assert assessment_state == "learning"
    assert status_text == "学习中"
    assert mastery_label == "A"

def test_evaluate_mastery_state_weak_low_overall_score():
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=65.0,
        question_count=5,
        attempt_count=4,
        latest_score=80.0,
        has_activity=True
    )
    assert assessment_state == "weak"
    assert status_text == "薄弱"
    assert mastery_label == "C"

def test_evaluate_mastery_state_weak_low_latest_score():
    # Even if overall is decent, if latest < 60, it's weak
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=75.0,
        question_count=5,
        attempt_count=4,
        latest_score=50.0,
        has_activity=True
    )
    assert assessment_state == "weak"
    assert status_text == "薄弱"
    assert mastery_label == "B"

def test_evaluate_mastery_state_learning():
    # Between 70 and 80, and latest >= 60
    assessment_state, status_text, mastery_label = evaluate_mastery_state(
        score=75.0,
        question_count=5,
        attempt_count=3,
        latest_score=75.0,
        has_activity=True
    )
    assert assessment_state == "learning"
    assert status_text == "学习中"
    assert mastery_label == "B"

def test_summarize_attempt_answers_tracks_latest_score_per_knowledge_point():
    base_time = datetime(2023, 1, 15, 12, 0)
    rows = [
        ("变量", True, "s1", 30, base_time),
        ("变量", True, "s1", 30, base_time),
        ("变量", True, "s2", 20, base_time + timedelta(hours=1)),
        ("变量", False, "s2", 20, base_time + timedelta(hours=1)),
    ]

    attempts = summarize_attempt_answers(rows)

    assert attempts["变量"]["total"] == 4
    assert attempts["变量"]["correct"] == 3
    assert attempts["变量"]["duration"] == 50
    assert attempts["变量"]["latest_score"] == 50.0
