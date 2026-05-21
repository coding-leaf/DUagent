import unittest
from pathlib import Path
import subprocess
import sys

from pydantic import ValidationError

from agent_service.schemas.profile import (
    CognitiveBlindspot,
    DriveIntent,
    GuidanceLevelSuggestion,
    KnowledgeCoordinate,
)
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


if __name__ == "__main__":
    unittest.main()
