from pathlib import Path
from typing import Any


WORDLIST_PATH = Path(__file__).resolve().parents[3] / "config" / "sensitive_words.txt"


class SensitiveContentError(ValueError):
    pass


def count_sensitive_matches(value: Any) -> int:
    text = _student_visible_text(value)
    return sum(text.count(word) for word in _words())


def ensure_student_visible_content_safe(value: Any) -> None:
    if count_sensitive_matches(value):
        raise SensitiveContentError("sensitive_content_detected")


def _words() -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in WORDLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _student_visible_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        return _student_visible_text(value.model_dump())
    if isinstance(value, dict):
        return "\n".join(_student_visible_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_student_visible_text(item) for item in value)
    return str(value)
