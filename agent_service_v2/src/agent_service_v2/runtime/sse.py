from __future__ import annotations

import json

from agent_service_v2.runtime.edu_events import EduEvent


def format_sse(event: EduEvent) -> str:
    return f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
