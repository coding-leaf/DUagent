from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentSafetyReview:
    passed: bool
    risk_level: str
    categories: list[str] = field(default_factory=list)
    reason: str = ""
    action: str = "allow"
    confidence: float = 0.0
    scope: str = "content_safety_only"
    knowledge_reviewed: bool = False
    reviewer: str = "external_model"
    match_count: int = 0

    @classmethod
    def skipped(cls, reason: str) -> "ContentSafetyReview":
        return cls(
            passed=True,
            risk_level="unknown",
            categories=[],
            reason=reason,
            action="allow",
            confidence=0.0,
            reviewer="skipped",
        )

    def normalized(self) -> "ContentSafetyReview":
        risk_level = self.risk_level if self.risk_level in _RISK_LEVELS else "unknown"
        if risk_level == "critical":
            action = "block"
        elif risk_level in {"medium", "high"}:
            action = "flag"
        else:
            action = "allow"
        return ContentSafetyReview(
            passed=action != "block" and self.passed,
            risk_level=risk_level,
            categories=list(self.categories or []),
            reason=self.reason or "",
            action=action,
            confidence=max(0.0, min(float(self.confidence or 0.0), 1.0)),
            scope="content_safety_only",
            knowledge_reviewed=False,
            reviewer=self.reviewer or "external_model",
            match_count=max(0, int(self.match_count or 0)),
        )

    def to_payload(self) -> dict:
        payload = {
            "passed": self.passed,
            "risk_level": self.risk_level,
            "categories": self.categories,
            "reason": self.reason,
            "action": self.action,
            "confidence": self.confidence,
            "scope": self.scope,
            "knowledge_reviewed": self.knowledge_reviewed,
            "reviewer": self.reviewer,
        }
        if self.reviewer == "local_wordlist":
            payload["match_count"] = self.match_count
        return payload


_RISK_LEVELS = {"none", "low", "medium", "high", "critical", "unknown"}
