from __future__ import annotations

from collections.abc import Iterable

from agent_service_v2.safety.local_wordlist import LocalSensitiveWordFilter


INTERNAL_DISCLOSURE_REPLACEMENT = "[内部信息已隐藏]"
_INTERNAL_ENDPOINT_PREFIX = "/internal/"
_ENDPOINT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789._~:/?#[]@!$&'()*+,;=%-"
)
_DEFAULT_PROTECTED_IDENTIFIERS = (
    "X-Internal-Agent-Token",
    "reference_solution",
    "hidden_inputs",
    "WORKBENCH_SYSTEM_PROMPT",
    "BACKEND_INTERNAL_AGENT_TOKEN",
    "LLM_API_KEY",
)


class InternalDisclosureFilter:
    def __init__(self, *, protected_identifiers: Iterable[str] = ()) -> None:
        identifiers = {*_DEFAULT_PROTECTED_IDENTIFIERS, *protected_identifiers}
        self.identifiers = tuple(sorted(identifiers, key=len, reverse=True))

    def filter(self, text: str) -> tuple[str, int]:
        return _consume(text, self.identifiers, final=True)

    def stream(self) -> "StreamingInternalDisclosureFilter":
        return StreamingInternalDisclosureFilter(self)


class StreamingInternalDisclosureFilter:
    def __init__(self, checker: InternalDisclosureFilter) -> None:
        self._checker = checker
        self._buffer = ""
        self.match_count = 0

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        rendered, consumed, matches = _consume_stream_prefix(
            self._buffer,
            self._checker.identifiers,
        )
        self._buffer = self._buffer[consumed:]
        self.match_count += matches
        return rendered

    def finish(self) -> str:
        rendered, matches = self._checker.filter(self._buffer)
        self._buffer = ""
        self.match_count += matches
        return rendered


class StudentOutputFilter:
    def __init__(self, *, protected_identifiers: Iterable[str] = ()) -> None:
        self._sensitive = LocalSensitiveWordFilter()
        self._internal = InternalDisclosureFilter(
            protected_identifiers=protected_identifiers,
        )

    def filter(self, text: str) -> tuple[str, int]:
        sensitive_text, sensitive_matches = self._sensitive.filter(text)
        filtered_text, internal_matches = self._internal.filter(sensitive_text)
        return filtered_text, sensitive_matches + internal_matches

    def stream(self) -> "StreamingStudentOutputFilter":
        return StreamingStudentOutputFilter(
            sensitive_stream=self._sensitive.stream(),
            internal_stream=self._internal.stream(),
        )


class StreamingStudentOutputFilter:
    def __init__(self, *, sensitive_stream, internal_stream) -> None:
        self._sensitive_stream = sensitive_stream
        self._internal_stream = internal_stream

    def feed(self, chunk: str) -> str:
        return self._internal_stream.feed(self._sensitive_stream.feed(chunk))

    def finish(self) -> str:
        sensitive_tail = self._sensitive_stream.finish()
        return self._internal_stream.feed(sensitive_tail) + self._internal_stream.finish()


def _consume(
    text: str,
    identifiers: tuple[str, ...],
    *,
    final: bool,
) -> tuple[str, int]:
    rendered, _consumed, matches = _consume_text(text, identifiers, final=final)
    return rendered, matches


def _consume_stream_prefix(
    text: str,
    identifiers: tuple[str, ...],
) -> tuple[str, int, int]:
    return _consume_text(text, identifiers, final=False)


def _consume_text(
    text: str,
    identifiers: tuple[str, ...],
    *,
    final: bool,
) -> tuple[str, int, int]:
    output: list[str] = []
    position = 0
    matches = 0
    while position < len(text):
        endpoint_end = _endpoint_end(text, position, final=final)
        if endpoint_end is None:
            break
        if endpoint_end > position:
            output.append(INTERNAL_DISCLOSURE_REPLACEMENT)
            position = endpoint_end
            matches += 1
            continue

        identifier = _matched_identifier(text, position, identifiers)
        if identifier is not None:
            output.append(INTERNAL_DISCLOSURE_REPLACEMENT)
            position += len(identifier)
            matches += 1
            continue
        if not final and _is_protected_prefix(text, position, identifiers):
            break
        output.append(text[position])
        position += 1
    return "".join(output), position, matches


def _endpoint_end(text: str, position: int, *, final: bool) -> int | None:
    remaining = text[position:]
    if _INTERNAL_ENDPOINT_PREFIX.startswith(remaining.lower()) and not final:
        return None
    if not remaining.lower().startswith(_INTERNAL_ENDPOINT_PREFIX):
        return position

    end = position + len(_INTERNAL_ENDPOINT_PREFIX)
    while end < len(text) and text[end] in _ENDPOINT_CHARS:
        end += 1
    if end == len(text) and not final:
        return None
    return end


def _matched_identifier(
    text: str,
    position: int,
    identifiers: tuple[str, ...],
) -> str | None:
    for identifier in identifiers:
        end = position + len(identifier)
        if text[position:end].lower() == identifier.lower():
            return identifier
    return None


def _is_protected_prefix(
    text: str,
    position: int,
    identifiers: tuple[str, ...],
) -> bool:
    remaining = text[position:]
    return any(identifier.lower().startswith(remaining.lower()) for identifier in identifiers)
