import unittest
from pathlib import Path
import subprocess
import sys

from pydantic import ValidationError

from agent_service.schemas.assessment import AssessmentQuestion, GeneratedQuestion, QuestionGenerateRequest
from agent_service.schemas.common import HealthData
from agent_service.schemas.learning_path import LearningPathNode
from agent_service.schemas.memory import ExtractedFact, MemoryMessage
from agent_service.schemas.profile import (
    CognitiveBlindspot,
    DriveIntent,
    GuidanceLevelSuggestion,
    KnowledgeCoordinate,
)
from agent_service.schemas.resources import ResourceGenerateRequest
from agent_service.schemas.tutoring import RecentMessage, TutoringUserProfile


class SchemaContractTests(unittest.TestCase):
    def test_agents_tutoring_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.tutoring"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agents_profile_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.profile"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agents_evaluation_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.evaluation"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agents_assessment_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.assessment"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agents_learning_path_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.learning_path"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agents_memory_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.memory"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_agents_resources_imports_from_agent_service_directory(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import agent_service.agents.resources"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_tutoring_user_profile_rejects_unknown_guidance_level(self) -> None:
        with self.assertRaises(ValidationError):
            TutoringUserProfile(guidance_level="L4")

    def test_recent_message_rejects_unknown_role(self) -> None:
        with self.assertRaises(ValidationError):
            RecentMessage(role="system", content="hello")

    def test_guidance_level_suggestion_rejects_unknown_recommended_level(self) -> None:
        with self.assertRaises(ValidationError):
            GuidanceLevelSuggestion(recommended="L4", reason="invalid")

    def test_knowledge_coordinate_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValidationError):
            KnowledgeCoordinate(name="一元二次方程", status="unknown")

    def test_cognitive_blindspot_rejects_unknown_severity(self) -> None:
        with self.assertRaises(ValidationError):
            CognitiveBlindspot(name="导数", error_count=2, severity="critical")

    def test_drive_intent_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValidationError):
            DriveIntent(type="random_mode", intensity=75)

    def test_health_data_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValidationError):
            HealthData(
                status="unknown",
                qdrant_connected=True,
                model_loaded=False,
                model_name="none",
                uptime_seconds=1,
            )

    def test_memory_message_rejects_unknown_role(self) -> None:
        with self.assertRaises(ValidationError):
            MemoryMessage(role="system", content="hello", timestamp="2026-05-22T00:00:00Z")

    def test_extracted_fact_rejects_unknown_fact_type(self) -> None:
        with self.assertRaises(ValidationError):
            ExtractedFact(content="fact", fact_type="other", confidence=0.8)

    def test_assessment_question_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValidationError):
            AssessmentQuestion(
                id="q1",
                type="essay",
                content="content",
                correct_answer="A",
                knowledge_point="导数",
            )

    def test_question_generate_request_rejects_unknown_difficulty(self) -> None:
        with self.assertRaises(ValidationError):
            QuestionGenerateRequest(user_id="u1", course_id="c1", difficulty="extreme")

    def test_generated_question_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValidationError):
            GeneratedQuestion(
                type="essay",
                content="content",
                answer="A",
                explanation="explanation",
                knowledge_point="导数",
            )

    def test_learning_path_node_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValidationError):
            LearningPathNode(status="unknown")

    def test_resource_generate_request_preserves_missing_resource_types(self) -> None:
        request = ResourceGenerateRequest(
            task_id="task-1",
            user_id="user-1",
            course_id="course-1",
            webhook_url="https://example.com/webhook",
        )
        self.assertIsNone(request.resource_types)

    def test_memory_message_requires_role(self) -> None:
        with self.assertRaises(ValidationError):
            MemoryMessage(content="hello", timestamp="2026-05-22T00:00:00Z")

    def test_memory_message_requires_content(self) -> None:
        with self.assertRaises(ValidationError):
            MemoryMessage(role="user", timestamp="2026-05-22T00:00:00Z")

    def test_memory_message_requires_timestamp(self) -> None:
        with self.assertRaises(ValidationError):
            MemoryMessage(role="user", content="hello")


if __name__ == "__main__":
    unittest.main()
