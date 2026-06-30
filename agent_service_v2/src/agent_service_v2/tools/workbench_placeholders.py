from __future__ import annotations


def read_learning_state(user_id: str, course_id: str | None = None) -> dict:
    return {
        "status": "placeholder",
        "tool": "read_learning_state",
        "user_id": user_id,
        "course_id": course_id,
    }


def draft_study_artifact(kind: str) -> dict:
    return {
        "status": "placeholder",
        "tool": "draft_study_artifact",
        "kind": kind,
    }


def review_grounding(summary: str) -> dict:
    return {
        "status": "placeholder",
        "tool": "review_grounding",
        "summary": summary,
    }
