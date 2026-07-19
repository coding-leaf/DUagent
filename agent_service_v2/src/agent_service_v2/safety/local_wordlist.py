from __future__ import annotations

from pathlib import Path


REPLACEMENT = "[内容已屏蔽]"
DEFAULT_WORDLIST = Path(__file__).resolve().parents[4] / "config" / "sensitive_words.txt"


class LocalSensitiveWordFilter:
    def __init__(self, path: str | Path = DEFAULT_WORDLIST) -> None:
        self.words = tuple(sorted(_load_words(Path(path)), key=len, reverse=True))
        self.max_word_length = max((len(word) for word in self.words), default=1)

    def matches(self, text: str) -> int:
        return _replace(text, self.words)[1]

    def filter(self, text: str) -> tuple[str, int]:
        return _replace(text, self.words)

    def stream(self) -> "StreamingSensitiveWordFilter":
        return StreamingSensitiveWordFilter(self)


class StreamingSensitiveWordFilter:
    def __init__(self, checker: LocalSensitiveWordFilter) -> None:
        self._checker = checker
        self._buffer = ""
        self.match_count = 0

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        safe_start_limit = max(0, len(self._buffer) - self._checker.max_word_length + 1)
        rendered, consumed, matches = _consume_prefix(
            self._buffer, self._checker.words, safe_start_limit
        )
        self._buffer = self._buffer[consumed:]
        self.match_count += matches
        return rendered

    def finish(self) -> str:
        rendered, matches = self._checker.filter(self._buffer)
        self._buffer = ""
        self.match_count += matches
        return rendered


def _load_words(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _replace(text: str, words: tuple[str, ...]) -> tuple[str, int]:
    rendered, _consumed, matches = _consume_prefix(text, words, len(text))
    return rendered, matches


def _consume_prefix(
    text: str, words: tuple[str, ...], start_limit: int
) -> tuple[str, int, int]:
    output: list[str] = []
    position = 0
    matches = 0
    while position < start_limit:
        matched = next((word for word in words if text.startswith(word, position)), None)
        if matched:
            output.append(REPLACEMENT)
            position += len(matched)
            matches += 1
        else:
            output.append(text[position])
            position += 1
    return "".join(output), position, matches
