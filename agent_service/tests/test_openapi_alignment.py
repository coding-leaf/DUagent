import json
import unittest
from pathlib import Path

from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest
from agent_service.schemas.profile import ProfileData, ProfileGenerateRequest
from agent_service.schemas.tutoring import TutoringChatRequest


OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs/20-agent-api/Agent-Service.openapi.json"


class OpenAPIAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.openapi = json.loads(OPENAPI_PATH.read_text())
        cls.schemas = cls.openapi["components"]["schemas"]

    def assert_schema_properties_match(self, model_schema: dict, openapi_name: str) -> None:
        openapi_schema = self.schemas[openapi_name]
        self.assertEqual(
            set(model_schema.get("properties", {})),
            set(openapi_schema.get("properties", {})),
            openapi_name,
        )
        self.assertEqual(
            set(model_schema.get("required", [])),
            set(openapi_schema.get("required", [])),
            openapi_name,
        )

    def test_tutoring_chat_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(TutoringChatRequest.model_json_schema(), "TutoringChatRequest")

    def test_tutoring_chat_request_nested_contract_matches_openapi(self) -> None:
        model_schema = TutoringChatRequest.model_json_schema()
        openapi_schema = self.schemas["TutoringChatRequest"]

        model_user_profile = model_schema["$defs"]["TutoringUserProfile"]
        openapi_user_profile = openapi_schema["properties"]["user_profile"]
        self.assertEqual(
            set(model_user_profile["properties"]),
            set(openapi_user_profile["properties"]),
        )
        self.assertEqual(
            set(model_user_profile.get("required", [])),
            set(openapi_user_profile.get("required", [])),
        )

        model_recent_message = model_schema["$defs"]["RecentMessage"]
        openapi_recent_message = openapi_schema["properties"]["recent_messages"]["items"]
        self.assertEqual(
            set(model_recent_message["properties"]),
            set(openapi_recent_message["properties"]),
        )

    def test_profile_generate_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(ProfileGenerateRequest.model_json_schema(), "ProfileGenerateRequest")

    def test_profile_data_matches_openapi(self) -> None:
        self.assert_schema_properties_match(ProfileData.model_json_schema(), "ProfileData")

    def test_evaluation_generate_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(EvaluationGenerateRequest.model_json_schema(), "EvaluationGenerateRequest")

    def test_evaluation_data_matches_openapi(self) -> None:
        self.assert_schema_properties_match(EvaluationData.model_json_schema(), "EvaluationData")


if __name__ == "__main__":
    unittest.main()
