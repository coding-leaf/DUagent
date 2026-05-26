"""Agent Service E2E Smoke — 一命令验证全部接口最小可用。

用法：./.venv/bin/python -m agent_service.tools.smoke_all
exit 0: 全部 PASS
exit 1: 至少一个 FAIL
"""

import json


def main() -> int:
    from agent_service.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    results: dict[str, bool] = {}

    # ── health ──────────────────────────────────────────────────────
    try:
        r = client.get("/agent/v1/health")
        data = r.json()
        results["health"] = r.status_code == 200 and data["data"]["status"] in {"healthy", "degraded"}
    except Exception:
        results["health"] = False

    # ── assessment/generate-questions ───────────────────────────────
    try:
        r = client.post("/agent/v1/assessment/generate-questions", json={
            "user_id": "smoke",
            "course_id": "smoke-course",
            "knowledge_point": "一次函数",
            "count": 2,
        })
        data = r.json()
        results["assessment/generate-questions"] = r.status_code == 200 and len(data["data"]["questions"]) > 0
    except Exception:
        results["assessment/generate-questions"] = False

    # ── assessment/evaluate ─────────────────────────────────────────
    try:
        r = client.post("/agent/v1/assessment/evaluate", json={
            "user_id": "smoke",
            "course_id": "smoke-course",
            "quiz_id": "smoke-quiz",
            "questions": [{
                "id": "q1", "type": "single_choice",
                "content": "1+1=?",
                "correct_answer": "B",
                "knowledge_point": "加法",
            }],
            "answers": [{"question_id": "q1", "answer": "A"}],
        })
        data = r.json()
        results["assessment/evaluate"] = r.status_code == 200 and len(data["data"]["per_question_results"]) > 0
    except Exception:
        results["assessment/evaluate"] = False

    # ── profile/generate ────────────────────────────────────────────
    try:
        r = client.post("/agent/v1/profile/generate", json={
            "user_id": "smoke",
            "course_id": "smoke-course",
            "quiz_history": [
                {"score": 90.0, "chapter": "函数", "created_at": "2026-05-20T10:00:00Z"},
                {"score": 60.0, "chapter": "导数", "created_at": "2026-05-21T10:00:00Z"},
            ],
            "resource_usage_stats": {
                "video_count": 2, "document_count": 4, "code_count": 1, "quiz_count": 3,
            },
            "drive_intent_data": {"recent_7d_sessions": 4, "recent_7d_duration": 180},
        })
        data = r.json()
        results["profile/generate"] = r.status_code == 200 and data["data"]["modal_preference"] is not None
    except Exception:
        results["profile/generate"] = False

    # ── evaluation/generate ─────────────────────────────────────────
    try:
        r = client.post("/agent/v1/evaluation/generate", json={
            "user_id": "smoke",
            "course_id": "smoke-course",
            "learning_progress": {
                "chapter_progress": [
                    {"chapter": "函数", "completion_rate": 80.0, "time_spent": 120},
                    {"chapter": "导数", "completion_rate": 40.0, "time_spent": 60},
                ],
            },
            "quiz_results": [
                {"chapter": "函数", "score": 90.0, "created_at": "2026-05-20T10:00:00Z"},
                {"chapter": "导数", "score": 55.0, "created_at": "2026-05-21T10:00:00Z"},
            ],
            "resource_usage": {"by_type": {"document": 3, "video": 1}},
        })
        data = r.json()
        results["evaluation/generate"] = r.status_code == 200 and data["data"]["progress_table"] is not None
    except Exception:
        results["evaluation/generate"] = False

    # ── learning-path/generate ──────────────────────────────────────
    try:
        r = client.post("/agent/v1/learning-path/generate", json={
            "user_id": "smoke",
            "course_id": "smoke-course",
            "knowledge_graph": {
                "nodes": [
                    {"id": "n1", "name": "函数", "chapter": "函数"},
                    {"id": "n2", "name": "导数", "chapter": "导数"},
                ],
                "edges": [{"from": "n1", "to": "n2"}],
            },
            "profile": {},
            "evaluation": {},
        })
        data = r.json()
        results["learning-path/generate"] = r.status_code == 200 and len(data["data"]["nodes"]) > 0
    except Exception:
        results["learning-path/generate"] = False

    # ── memory/compress ─────────────────────────────────────────────
    try:
        r = client.post("/agent/v1/memory/compress", json={
            "user_id": "smoke",
            "conversation_id": "smoke-conv",
            "messages_to_compress": [
                {"role": "user", "content": "我总是在导数定义上卡住", "timestamp": "2026-05-22T10:00:00Z"},
            ],
        })
        data = r.json()
        results["memory/compress"] = r.status_code == 200 and data["data"]["new_summary"] is not None
    except Exception:
        results["memory/compress"] = False

    # ── resources/generate ──────────────────────────────────────────
    try:
        r = client.post("/agent/v1/resources/generate", json={
            "task_id": "smoke-task",
            "user_id": "smoke",
            "course_id": "smoke-course",
            "webhook_url": "http://localhost:9999/webhook",
            "resource_types": ["document"],
        })
        data = r.json()
        results["resources/generate"] = r.status_code == 202 and data["data"]["task_id"] == "smoke-task"
    except Exception:
        results["resources/generate"] = False

    # ── tutoring/chat SSE ───────────────────────────────────────────
    try:
        r = client.post("/agent/v1/tutoring/chat", json={
            "user_id": "smoke",
            "course_id": "smoke-course",
            "message": "帮我讲一下一次函数",
            "scope": "course",
            "user_profile": {
                "guidance_level": "L2",
                "knowledge_weak": ["一次函数"],
                "knowledge_mastered": [],
            },
        })
        results["tutoring/chat"] = r.status_code == 200 and "text/event-stream" in r.headers.get("content-type", "")
    except Exception:
        results["tutoring/chat"] = False

    # ── Report ──────────────────────────────────────────────────────
    all_pass = all(results.values())
    print(json.dumps({
        "status": "PASS" if all_pass else "FAIL",
        "results": {k: "PASS" if v else "FAIL" for k, v in results.items()},
    }, ensure_ascii=False, indent=2))

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
