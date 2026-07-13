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


def test_backend_content_safety_covers_expanded_categories():
    samples = [
        "枪支交易",
        "制毒教程",
        "赌博平台代理",
        "杀猪盘话术",
        "钓鱼网站搭建",
        "恐怖组织招募",
        "论文代写",
        "买卖公民信息",
    ]

    assert all(count_sensitive_matches(sample) == 1 for sample in samples)
    assert count_sensitive_matches("禁毒教育、反诈骗课程与心理健康辅导") == 0
