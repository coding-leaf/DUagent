import pytest
from pydantic import ValidationError

from agent_service_v2.tools.learning_progress import build_learning_progress_tools
from agent_service_v2.tools.personal_choice_quiz import build_personal_choice_quiz_tools
from agent_service_v2.tools.personal_code_problem import build_personal_code_problem_tools
from agent_service_v2.tools.input_models import (
    ArtifactFileInput,
    PersonalCodeProblemInput,
    RAGRetrieveInput,
)


def _tool(tools, name):
    return next(item for item in tools if item.name == name)


def test_choice_quiz_schema_is_nested_and_constrained():
    tool = build_personal_choice_quiz_tools(
        client=None,
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
        run_id="run-1",
    )[0]
    schema = tool.input_schema
    question = schema["$defs"]["ChoiceQuestionInput"]
    option = schema["$defs"]["ChoiceOptionInput"]

    assert set(schema["required"]) == {"title", "chapter", "knowledge_point", "questions"}
    assert schema["properties"]["questions"]["minItems"] == 1
    assert schema["properties"]["questions"]["maxItems"] == 8
    assert question["properties"]["type"]["enum"] == ["single_choice", "multi_choice"]
    assert question["properties"]["difficulty"]["enum"] == ["easy", "medium", "hard"]
    assert question["properties"]["options"]["minItems"] == 2
    assert option["properties"]["key"]["minLength"] == 1
    assert "user_id" not in schema["properties"]


def test_code_problem_schema_has_language_enum_and_input_limits():
    tool = build_personal_code_problem_tools(
        client=None,
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
        run_id="run-1",
    )[0]
    schema = tool.input_schema

    assert tool.name == "publish_personal_code_problem"
    assert schema["properties"]["language"]["enum"] == [
        "c", "cpp", "python", "java", "go", "javascript"
    ]
    assert schema["properties"]["public_inputs"]["minItems"] == 1
    assert schema["properties"]["hidden_inputs"]["minItems"] == 1
    assert schema["properties"]["public_inputs"]["maxItems"] == 7
    assert schema["properties"]["hidden_inputs"]["maxItems"] == 7
    assert schema["properties"]["statement"]["maxLength"] == 10000
    assert schema["properties"]["starter_code"]["maxLength"] == 20000
    assert schema["properties"]["reference_solution"]["maxLength"] == 30000
    assert "run_id" not in schema["properties"]


def test_code_problem_input_requires_backend_case_limit_and_complete_entrypoint():
    common = {
        "title": "求和",
        "statement": "读取两个整数并输出和。",
        "language": "c",
        "starter_code": "",
        "public_inputs": ["1 2\n"],
        "hidden_inputs": ["2 3\n"],
    }

    with pytest.raises(ValidationError, match="complete executable program"):
        PersonalCodeProblemInput(
            **common,
            reference_solution="int add(int a, int b) { return a + b; }",
        )

    with pytest.raises(ValidationError, match="at most 8"):
        PersonalCodeProblemInput(
            **{
                **common,
                "public_inputs": [f"{value}\n" for value in range(7)],
                "hidden_inputs": ["7\n", "8\n"],
            },
            reference_solution="int main(void) { return 0; }",
        )

    valid = PersonalCodeProblemInput(
        **common,
        reference_solution="int main(void) { return 0; }",
    )
    assert valid.language == "c"


def test_recent_answers_schema_exposes_scope_and_cross_field_contract():
    tool = _tool(
        build_learning_progress_tools(client=None, user_id="u1", course_id="c1"),
        "read_recent_answers",
    )
    schema = tool.input_schema

    assert schema["properties"]["scope"]["enum"] == [
        "course", "node", "knowledge_point"
    ]
    assert schema["properties"]["limit"]["minimum"] == 1
    assert schema["properties"]["limit"]["maximum"] == 10
    assert "user_id" not in schema["properties"]


def test_rag_and_artifact_models_expose_ranges_and_enums():
    rag = RAGRetrieveInput.tool_schema()
    artifact = ArtifactFileInput.tool_schema()

    assert rag["properties"]["limit"]["minimum"] == 1
    assert rag["properties"]["limit"]["maximum"] == 10
    assert artifact["properties"]["artifact_type"]["enum"] == ["Markdown", "Mermaid"]
