"""Agent Service E2E Smoke - one command checks all endpoint handlers.

Usage: ./.venv/bin/python -m agent_service.tools.smoke_all
exit 0: all PASS
exit 1: at least one FAIL
"""

import asyncio
import json


class _SmokeProviders:
    chat = None
    embedding = None
    reranker = None


def main() -> int:
    return asyncio.run(_main_async())


async def _main_async() -> int:
    from fastapi import BackgroundTasks

    from agent_service.api.v1 import assessment, evaluation, health, learning_path, memory, profile, resources, tutoring
    from agent_service.agents import memory as memory_agent
    from agent_service.core import ai as core_ai
    from agent_service.schemas.assessment import AssessmentEvaluateRequest, QuestionGenerateRequest
    from agent_service.schemas.evaluation import EvaluationGenerateRequest
    from agent_service.schemas.learning_path import LearningPathGenerateRequest
    from agent_service.schemas.memory import MemoryCompressRequest
    from agent_service.schemas.profile import ProfileGenerateRequest
    from agent_service.schemas.resources import ResourceGenerateRequest
    from agent_service.schemas.tutoring import TutoringChatRequest

    def _get_smoke_providers() -> _SmokeProviders:
        return _SmokeProviders()

    def _build_smoke_health_data() -> dict:
        return {
            "status": "healthy",
            "qdrant_connected": True,
            "model_loaded": False,
            "model_name": "",
            "uptime_seconds": 0,
        }

    for module in (assessment, evaluation, learning_path, memory, profile, core_ai, memory_agent):
        module.get_ai_providers = _get_smoke_providers
    health.build_health_data = _build_smoke_health_data

    results: dict[str, bool] = {}
    details: dict[str, dict] = {}

    # -- health -------------------------------------------------------
    try:
        response = await health.health_check()
        results["health"] = response.code == 200 and response.data.status in {"healthy", "degraded"}
    except Exception:
        results["health"] = False

    # -- assessment/generate-questions -------------------------------
    try:
        response = await assessment.generate_questions(
            QuestionGenerateRequest(
                user_id="smoke",
                course_id="smoke-course",
                knowledge_point="一次函数",
                count=2,
            )
        )
        results["assessment/generate-questions"] = response.code == 200 and len(response.data.questions) > 0
    except Exception:
        results["assessment/generate-questions"] = False

    # -- assessment/evaluate -----------------------------------------
    try:
        response = await assessment.evaluate_assessment(
            AssessmentEvaluateRequest(
                user_id="smoke",
                course_id="smoke-course",
                quiz_id="smoke-quiz",
                questions=[
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "content": "1+1=?",
                        "correct_answer": "B",
                        "knowledge_point": "加法",
                    }
                ],
                answers=[{"question_id": "q1", "answer": "A"}],
            )
        )
        results["assessment/evaluate"] = response.code == 200 and len(response.data.per_question_results) > 0
    except Exception:
        results["assessment/evaluate"] = False

    # -- profile/generate --------------------------------------------
    try:
        response = await profile.generate_profile(
            ProfileGenerateRequest(
                user_id="smoke",
                course_id="smoke-course",
                quiz_history=[
                    {"score": 90.0, "chapter": "函数", "created_at": "2026-05-20T10:00:00Z"},
                    {"score": 60.0, "chapter": "导数", "created_at": "2026-05-21T10:00:00Z"},
                ],
                resource_usage_stats={
                    "video_count": 2,
                    "document_count": 4,
                    "code_count": 1,
                    "quiz_count": 3,
                },
                drive_intent_data={"recent_7d_sessions": 4, "recent_7d_duration": 180},
            )
        )
        results["profile/generate"] = response.code == 200 and response.data.modal_preference is not None
    except Exception:
        results["profile/generate"] = False

    # -- evaluation/generate -----------------------------------------
    try:
        response = await evaluation.generate_evaluation(
            EvaluationGenerateRequest(
                user_id="smoke",
                course_id="smoke-course",
                learning_progress={
                    "chapter_progress": [
                        {"chapter": "函数", "completion_rate": 80.0, "time_spent": 120},
                        {"chapter": "导数", "completion_rate": 40.0, "time_spent": 60},
                    ],
                },
                quiz_results=[
                    {"chapter": "函数", "score": 90.0, "created_at": "2026-05-20T10:00:00Z"},
                    {"chapter": "导数", "score": 55.0, "created_at": "2026-05-21T10:00:00Z"},
                ],
                resource_usage={"by_type": {"document": 3, "video": 1}},
            )
        )
        results["evaluation/generate"] = response.code == 200 and response.data.progress_table is not None
    except Exception:
        results["evaluation/generate"] = False

    # -- learning-path/generate --------------------------------------
    try:
        response = await learning_path.generate_learning_path(
            LearningPathGenerateRequest(
                user_id="smoke",
                course_id="smoke-course",
                knowledge_graph={
                    "nodes": [
                        {"id": "n1", "name": "函数", "chapter": "函数"},
                        {"id": "n2", "name": "导数", "chapter": "导数"},
                    ],
                    "edges": [{"from": "n1", "to": "n2"}],
                },
                profile={},
                evaluation={},
            )
        )
        results["learning-path/generate"] = response.code == 200 and len(response.data.nodes) > 0
    except Exception:
        results["learning-path/generate"] = False

    # -- memory/compress ---------------------------------------------
    try:
        response = await memory.compress_memory(
            MemoryCompressRequest(
                user_id="smoke",
                conversation_id="smoke-conv",
                messages_to_compress=[
                    {
                        "role": "user",
                        "content": "我总是在导数定义上卡住",
                        "timestamp": "2026-05-22T10:00:00Z",
                    }
                ],
            )
        )
        results["memory/compress"] = response.code == 200 and response.data.new_summary is not None
    except Exception:
        results["memory/compress"] = False

    # -- resources/generate ------------------------------------------
    try:
        response = await resources.generate_resources(
            ResourceGenerateRequest(
                task_id="smoke-task",
                user_id="smoke",
                course_id="smoke-course",
                webhook_url="http://localhost:9999/webhook",
                resource_types=["document"],
            ),
            BackgroundTasks(),
        )
        accepted = response.code == 202 and response.data.task_id == "smoke-task"
        workflow_detail = await _smoke_resources_multi_agent_path()
        results["resources/generate"] = accepted and workflow_detail["status"] == "PASS"
        details["resources/generate"] = {
            "accepted": accepted,
            **workflow_detail,
        }
    except Exception:
        results["resources/generate"] = False
        details["resources/generate"] = {"accepted": False, "path": "error"}

    # -- tutoring/chat SSE -------------------------------------------
    try:
        response = await tutoring.tutoring_chat(
            TutoringChatRequest(
                user_id="smoke",
                course_id="smoke-course",
                message="帮我讲一下一次函数",
                scope="course",
                user_profile={
                    "guidance_level": "L2",
                    "knowledge_weak": ["一次函数"],
                    "knowledge_mastered": [],
                },
            )
        )
        results["tutoring/chat"] = response.media_type == "text/event-stream"
    except Exception:
        results["tutoring/chat"] = False

    all_pass = all(results.values())
    print(
        json.dumps(
            {
                "status": "PASS" if all_pass else "FAIL",
                "results": {key: "PASS" if value else "FAIL" for key, value in results.items()},
                "details": details,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0 if all_pass else 1


async def _smoke_resources_multi_agent_path() -> dict:
    from agent_service.agents.resources_workflow import run_multi_agent_resource_workflow
    from agent_service.schemas.resources import ResourceGenerateRequest
    from agent_service.tools.smoke_resources_workflow import (
        _FakeResourcesChatProvider,
        _evaluate_payload,
    )

    chat = _FakeResourcesChatProvider()
    payload = await run_multi_agent_resource_workflow(
        ResourceGenerateRequest(
            task_id="smoke-resources-workflow",
            user_id="smoke",
            course_id="smoke-course",
            webhook_url="http://localhost:9999/webhook",
            chapter="函数",
            knowledge_point="一次函数",
            resource_types=["document", "mindmap", "reading", "code"],
        ),
        chat,
        embedding_provider=None,
    )
    detail = _evaluate_payload(payload)
    detail["path"] = "multi_agent" if payload is not None else "fallback_required"
    detail["llm_calls"] = chat.calls
    return detail


if __name__ == "__main__":
    raise SystemExit(main())
