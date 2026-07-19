from __future__ import annotations

from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.safety.content_review_middleware import ContentSafetyReviewer
from agent_service_v2.safety.local_wordlist import (
    LocalSensitiveWordFilter,
    StreamingSensitiveWordFilter,
)
from agent_service_v2.safety.schemas import ContentSafetyReview
from agent_service_v2.session.run_bus import WorkbenchRun, WorkbenchRunBus
from agent_service_v2.workspaces.run_store import WorkbenchRunStore


REFUSAL_TEXT = "抱歉，我无法回答你的问题。"


class WorkbenchSafetyGuard:
    def __init__(
        self,
        *,
        reviewer: ContentSafetyReviewer,
        run_bus: WorkbenchRunBus,
    ) -> None:
        self._reviewer = reviewer
        self._run_bus = run_bus
        self._local = LocalSensitiveWordFilter()

    async def review_input(self, message: str) -> ContentSafetyReview:
        return await self._reviewer.review(f"用户请求：{message}")

    def start_output_scan(self) -> StreamingSensitiveWordFilter:
        return self._local.stream()

    def review_output(
        self,
        scanner: StreamingSensitiveWordFilter,
        chunk: str,
        *,
        final: bool = False,
    ) -> ContentSafetyReview | None:
        if final:
            scanner.finish()
        else:
            scanner.feed(chunk)
        if scanner.match_count == 0:
            return None
        return self._reviewer.local_block_review(scanner.match_count)

    async def publish_final_review(
        self,
        *,
        run: WorkbenchRun,
        run_store: WorkbenchRunStore,
        content: str,
    ) -> None:
        review = await self._reviewer.review(content)
        self._publish_review(run=run, run_store=run_store, review=review)

    def publish_blocked(
        self,
        *,
        run: WorkbenchRun,
        run_store: WorkbenchRunStore,
        review: ContentSafetyReview,
        publish_started: bool,
    ) -> None:
        if publish_started:
            self._append(
                run,
                run_store,
                EduEventType.WORKFLOW_STARTED,
                {"reply_id": None, "session_id": run.conversation_id},
            )
        self._publish_review(run=run, run_store=run_store, review=review)
        self._append(
            run,
            run_store,
            EduEventType.TEXT_DELTA,
            {"delta": REFUSAL_TEXT},
        )
        self._append(run, run_store, EduEventType.WORKFLOW_COMPLETED, {})
        run_store.write_state(
            run.run_id,
            {"status": "completed", "conversation_id": run.conversation_id},
        )
        self._run_bus.complete(run.run_id)

    def _publish_review(
        self,
        *,
        run: WorkbenchRun,
        run_store: WorkbenchRunStore,
        review: ContentSafetyReview,
    ) -> None:
        payload = review.to_payload()
        run_store.write_review(run.run_id, payload)
        self._append(
            run,
            run_store,
            EduEventType.CONTENT_SAFETY_REVIEWED,
            payload,
        )

    def _append(
        self,
        run: WorkbenchRun,
        run_store: WorkbenchRunStore,
        event_type: EduEventType,
        payload: dict,
    ) -> None:
        event = self._run_bus.publish(run.run_id, event_type, payload)
        run_store.append_event(run.run_id, event.to_dict())
