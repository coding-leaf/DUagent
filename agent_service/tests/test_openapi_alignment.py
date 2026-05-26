import json
import unittest
from pathlib import Path

from agent_service.main import app
from agent_service.schemas.assessment import (
    AssessmentEvaluateRequest,
    AssessmentResult,
    QuestionGenerateRequest,
    QuestionGenerateResult,
)
from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest
from agent_service.schemas.learning_path import LearningPathData, LearningPathGenerateRequest
from agent_service.schemas.memory import MemoryCompressRequest, MemoryCompressResult
from agent_service.schemas.profile import ProfileData, ProfileGenerateRequest
from agent_service.schemas.resources import ResourceGenerateRequest
from agent_service.schemas.tutoring import TutoringChatRequest


OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs/20-agent-api/Agent-Service.openapi.json"


class OpenAPIAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.openapi = json.loads(OPENAPI_PATH.read_text())
        cls.schemas = cls.openapi["components"]["schemas"]
        cls.app_openapi = app.openapi()

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

    def resolve_app_schema(self, schema: dict) -> dict:
        if "$ref" not in schema:
            return schema
        ref_name = schema["$ref"].split("/")[-1]
        return self.app_openapi["components"]["schemas"][ref_name]

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

    def test_app_openapi_contains_expected_paths(self) -> None:
        self.assertIn("/agent/v1/tutoring/chat", self.app_openapi["paths"])
        self.assertIn("/agent/v1/profile/generate", self.app_openapi["paths"])
        self.assertIn("/agent/v1/evaluation/generate", self.app_openapi["paths"])
        self.assertIn("/agent/v1/assessment/evaluate", self.app_openapi["paths"])
        self.assertIn("/agent/v1/assessment/generate-questions", self.app_openapi["paths"])
        self.assertIn("/agent/v1/learning-path/generate", self.app_openapi["paths"])
        self.assertIn("/agent/v1/resources/generate", self.app_openapi["paths"])
        self.assertIn("/agent/v1/memory/compress", self.app_openapi["paths"])

    def test_app_openapi_profile_generate_uses_json_wrapper(self) -> None:
        response_schema = self.app_openapi["paths"]["/agent/v1/profile/generate"]["post"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        response_schema = self.resolve_app_schema(response_schema)
        self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})

    def test_app_openapi_evaluation_generate_uses_json_wrapper(self) -> None:
        response_schema = self.app_openapi["paths"]["/agent/v1/evaluation/generate"]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        response_schema = self.resolve_app_schema(response_schema)
        self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})

    def test_app_openapi_health_uses_json_wrapper(self) -> None:
        response_schema = self.app_openapi["paths"]["/agent/v1/health"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        response_schema = self.resolve_app_schema(response_schema)
        self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})

    def test_app_openapi_tutoring_chat_uses_sse(self) -> None:
        response_content = self.app_openapi["paths"]["/agent/v1/tutoring/chat"]["post"]["responses"]["200"]["content"]
        self.assertIn("text/event-stream", response_content)

    def test_app_openapi_assessment_routes_use_json_wrapper(self) -> None:
        for path in ("/agent/v1/assessment/evaluate", "/agent/v1/assessment/generate-questions"):
            response_schema = self.app_openapi["paths"][path]["post"]["responses"]["200"]["content"]["application/json"][
                "schema"
            ]
            response_schema = self.resolve_app_schema(response_schema)
            self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})

    def test_app_openapi_learning_path_uses_json_wrapper(self) -> None:
        response_schema = self.app_openapi["paths"]["/agent/v1/learning-path/generate"]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        response_schema = self.resolve_app_schema(response_schema)
        self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})

    def test_app_openapi_resources_generate_returns_202_wrapper(self) -> None:
        responses = self.app_openapi["paths"]["/agent/v1/resources/generate"]["post"]["responses"]
        self.assertIn("202", responses)
        response_schema = responses["202"]["content"]["application/json"]["schema"]
        response_schema = self.resolve_app_schema(response_schema)
        self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})

    def test_assessment_evaluate_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(AssessmentEvaluateRequest.model_json_schema(), "AssessmentEvaluateRequest")

    def test_assessment_result_matches_openapi(self) -> None:
        self.assert_schema_properties_match(AssessmentResult.model_json_schema(), "AssessmentResult")

    def test_question_generate_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(QuestionGenerateRequest.model_json_schema(), "QuestionGenerateRequest")

    def test_question_generate_result_matches_openapi(self) -> None:
        self.assert_schema_properties_match(QuestionGenerateResult.model_json_schema(), "QuestionGenerateResult")

    def test_learning_path_generate_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(LearningPathGenerateRequest.model_json_schema(), "LearningPathGenerateRequest")

    def test_learning_path_data_matches_openapi(self) -> None:
        self.assert_schema_properties_match(LearningPathData.model_json_schema(), "LearningPathData")

    def test_memory_compress_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(MemoryCompressRequest.model_json_schema(), "MemoryCompressRequest")

    def test_memory_compress_result_matches_openapi(self) -> None:
        self.assert_schema_properties_match(MemoryCompressResult.model_json_schema(), "MemoryCompressResult")

    def test_resource_generate_request_matches_openapi(self) -> None:
        self.assert_schema_properties_match(ResourceGenerateRequest.model_json_schema(), "ResourceGenerateRequest")

    def test_app_openapi_memory_compress_uses_json_wrapper(self) -> None:
        response_schema = self.app_openapi["paths"]["/agent/v1/memory/compress"]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        response_schema = self.resolve_app_schema(response_schema)
        self.assertEqual(set(response_schema["properties"]), {"code", "message", "data"})


if __name__ == "__main__":
    unittest.main()
