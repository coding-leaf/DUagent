from __future__ import annotations


class UnsupportedCodeLanguageError(ValueError):
    """Raised when a value cannot be mapped to a supported teaching language."""


SUPPORTED_CODE_LANGUAGES = (
    "c",
    "cpp",
    "python",
    "java",
    "go",
    "javascript",
)

_LANGUAGE_ALIASES = {
    "c": "c",
    "c++": "cpp",
    "cpp": "cpp",
    "python": "python",
    "python3": "python",
    "python 3": "python",
    "java": "java",
    "go": "go",
    "golang": "go",
    "javascript": "javascript",
    "js": "javascript",
    "node": "javascript",
    "node.js": "javascript",
}

_JUDGE0_LANGUAGE_IDS = {
    "c": 50,
    "cpp": 54,
    "python": 71,
    "java": 62,
    "go": 60,
    "javascript": 63,
}


def normalize_code_language(value: str) -> str:
    """Return the canonical teaching-language identifier for user-facing input."""
    if not isinstance(value, str):
        raise UnsupportedCodeLanguageError("language must be a string")

    canonical = _LANGUAGE_ALIASES.get(value.strip().casefold())
    if canonical is None:
        raise UnsupportedCodeLanguageError(f"unsupported language: {value}")
    return canonical


def judge0_language_id(value: str) -> int:
    """Resolve a supported teaching language to this deployment's Judge0 ID."""
    return _JUDGE0_LANGUAGE_IDS[normalize_code_language(value)]
