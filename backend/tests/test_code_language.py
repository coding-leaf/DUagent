import pytest

from app.schemas.code_problem import CodeProblemDraft, CodeProblemTestInput
from app.services.code_language import (
    UnsupportedCodeLanguageError,
    judge0_language_id,
    normalize_code_language,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("C", "c"),
        ("C++", "cpp"),
        ("Python3", "python"),
        ("Java", "java"),
        ("Golang", "go"),
        ("Node.js", "javascript"),
    ],
)
def test_normalize_code_language_accepts_common_aliases(raw, expected):
    assert normalize_code_language(raw) == expected


def test_normalize_code_language_rejects_unknown_value():
    with pytest.raises(UnsupportedCodeLanguageError):
        normalize_code_language("rust")


def test_judge0_language_id_uses_canonical_language():
    assert judge0_language_id("C++") == 54


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("C++", "cpp"), ("Python 3", "python"), ("Node.js", "javascript")],
)
def test_code_problem_draft_stores_canonical_language(raw, expected):
    draft = CodeProblemDraft(
        title="Echo",
        statement="Read and write input.",
        language=raw,
        starter_code="print(input())",
        reference_solution="print(input())",
        test_inputs=[
            CodeProblemTestInput(stdin="shown\n", is_public=True),
            CodeProblemTestInput(stdin="hidden\n", is_public=False),
        ],
    )

    assert draft.language == expected
