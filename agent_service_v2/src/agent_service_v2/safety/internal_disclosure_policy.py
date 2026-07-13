from __future__ import annotations

import re
from collections.abc import Iterable

from agent_service_v2.safety.internal_disclosure_filter import (
    InternalDisclosureFilter,
    StudentOutputFilter,
)


SAFE_CAPABILITY_SUMMARY = (
    "我可以帮助你检索课程资料、分析学习情况、检查代码、推荐学习资源和创建练习。"
    "具体内部提示词、工具名称、参数及接口配置不对外公开。请直接告诉我你的学习目标。"
)

_SYSTEM_PROMPT_PATTERN = re.compile(
    r"(系统提示词|system\s+prompt)",
    re.IGNORECASE,
)
_PROBE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        _SYSTEM_PROMPT_PATTERN.pattern,
        r"(你的|内部|核心|所有).{0,12}(工具|tool|能力).{0,16}(参数|字段|名称|列表|schema|配置|定义)",
        r"你的.{0,8}(工具|能力).{0,8}(有哪些|是什么|列表)",
        r"你.{0,8}(有|具备|支持).{0,8}(哪些|什么)?.{0,8}(工具|能力)",
        r"(列出|展示|介绍|告诉|公开|完整).{0,16}(工具|tool).{0,16}(参数|字段|schema|定义|配置)?",
        r"(list|show|reveal|describe).{0,20}(tools?|functions?).{0,20}(schema|parameters?|arguments?)?",
        r"what.{0,16}(tools?|capabilit(?:y|ies)).{0,16}(have|available)?",
        r"你.{0,8}(能|可).{0,8}(哪些|什么).{0,8}(能力|工具)",
        r"(tool|function)[_ -]?(schema|parameters?|arguments?)",
    )
)

_SCHEMA_FIELDS = (
    "query",
    "limit",
    "limit_nodes",
    "scope",
    "node_id",
    "knowledge_point",
    "only_wrong",
    "code",
    "language",
    "stdin",
    "target",
    "goal",
    "resource_type",
    "filename",
    "content",
    "artifact_type",
    "memory_type",
)
_SCHEMA_FIELD_PATTERN = re.compile(
    r"(?:`|\|\s*)(?:" + "|".join(_SCHEMA_FIELDS) + r")(?:`|\s*\|)",
    re.IGNORECASE,
)
_SCHEMA_HEADER_PATTERN = re.compile(
    r"\|\s*(?:参数|字段|parameter|argument)s?\s*\|",
    re.IGNORECASE,
)


def is_internal_capability_probe(message: str) -> bool:
    normalized = " ".join(message.split())
    return any(pattern.search(normalized) for pattern in _PROBE_PATTERNS)


def contains_internal_schema_disclosure(
    text: str,
    *,
    protected_identifiers: Iterable[str],
) -> bool:
    internal_matches = InternalDisclosureFilter(
        protected_identifiers=protected_identifiers,
    ).filter(text)[1]
    if internal_matches:
        return True

    schema_fields = len(_SCHEMA_FIELD_PATTERN.findall(text))
    return schema_fields >= 2 or bool(
        schema_fields and _SCHEMA_HEADER_PATTERN.search(text)
    )


class StudentTextOutputGate:
    def __init__(
        self,
        *,
        request: str,
        protected_identifiers: Iterable[str] = (),
    ) -> None:
        self._protected_identifiers = tuple(protected_identifiers)
        self._buffer_for_review = is_internal_capability_probe(request)
        self._force_safe_summary = bool(_SYSTEM_PROMPT_PATTERN.search(request))
        self._raw_chunks: list[str] = []
        self._filter = StudentOutputFilter(
            protected_identifiers=self._protected_identifiers,
        )
        self._stream = self._filter.stream()

    def feed(self, chunk: str) -> str:
        if self._buffer_for_review:
            self._raw_chunks.append(chunk)
            return ""
        return self._stream.feed(chunk)

    def finish(self) -> str:
        if not self._buffer_for_review:
            return self._stream.finish()

        raw_text = "".join(self._raw_chunks)
        self._raw_chunks.clear()
        if self._force_safe_summary:
            return SAFE_CAPABILITY_SUMMARY
        if contains_internal_schema_disclosure(
            raw_text,
            protected_identifiers=self._protected_identifiers,
        ):
            return SAFE_CAPABILITY_SUMMARY
        return self._filter.filter(raw_text)[0]
