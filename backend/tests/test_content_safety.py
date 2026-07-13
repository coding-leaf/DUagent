import pytest

from app.services.content_safety import (
    SensitiveContentError,
    count_sensitive_matches,
    ensure_student_visible_content_safe,
)


def test_backend_content_safety_uses_versioned_wordlist():
    assert count_sensitive_matches("正常教学资料") == 0
    assert count_sensitive_matches({"title": "代考服务推广", "content": "买卖答案"}) == 2


def test_backend_content_safety_rejects_student_visible_draft():
    with pytest.raises(SensitiveContentError, match="sensitive_content_detected"):
        ensure_student_visible_content_safe({"statement": "介绍自杀方法"})
