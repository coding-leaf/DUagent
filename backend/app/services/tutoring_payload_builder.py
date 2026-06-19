"""Build the privacy-filtered Backend-to-Agent tutoring request."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.conversation import Conversation, Message
from app.models.others import UserProfile
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.tutoring_service import message_order_key


class TutoringPayloadBuilder:
    """Assemble Agent input from SQL using an explicit field allowlist."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build(
        self,
        *,
        user_id: str,
        scope: str,
        course_id: str | None,
        conversation_id: str,
        message: str,
        exclude_message_ids: set[str] | None = None,
    ) -> dict:
        payload: dict = {
            "user_id": user_id,
            "scope": scope,
            "message": message,
            "conversation_id": conversation_id,
            "active_kg_nodes": [],
        }
        if course_id:
            payload["course_id"] = course_id

        await self._add_course_context(payload, scope, course_id)
        await self._add_user_profile(payload, user_id, scope, course_id)
        await self._add_conversation_context(
            payload,
            conversation_id,
            exclude_message_ids or set(),
        )
        return payload

    async def _add_course_context(
        self,
        payload: dict,
        scope: str,
        course_id: str | None,
    ) -> None:
        if scope != "course" or not course_id:
            return

        offering = (
            await self.db.execute(
                select(CourseOffering).where(CourseOffering.id == course_id)
            )
        ).scalar_one_or_none()
        catalog_id = offering.catalog_id if offering else None
        if not catalog_id:
            return

        payload["catalog_id"] = catalog_id
        catalog = (
            await self.db.execute(
                select(CourseCatalog).where(CourseCatalog.id == catalog_id)
            )
        ).scalar_one_or_none()
        if not catalog or not catalog.kg_host_course_id:
            return

        active_graph = await get_active_knowledge_graph(
            self.db,
            catalog.kg_host_course_id,
        )
        graph_nodes = (
            active_graph.nodes
            if active_graph and isinstance(active_graph.nodes, list)
            else []
        )
        payload["active_kg_nodes"] = [
            {
                "id": node.get("id"),
                "name": node.get("name"),
                "chapter": node.get("chapter"),
            }
            for node in graph_nodes
            if isinstance(node, dict)
        ]

    async def _add_user_profile(
        self,
        payload: dict,
        user_id: str,
        scope: str,
        course_id: str | None,
    ) -> None:
        if scope != "course" or not course_id:
            payload["user_profile"] = {"guidance_level": "L2"}
            return

        profile = (
            await self.db.execute(
                select(UserProfile).where(
                    UserProfile.user_id == user_id,
                    UserProfile.course_id == course_id,
                    UserProfile.is_deleted == False,
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            payload["user_profile"] = {"guidance_level": "L2"}
            return

        knowledge_coordinates = [
            item
            for item in (profile.knowledge_coordinates or [])
            if isinstance(item, dict)
        ]
        payload["user_profile"] = {
            "guidance_level": profile.guidance_level_current,
            "modal_preference": profile.modal_preference,
            "knowledge_mastered": [
                item["name"]
                for item in knowledge_coordinates
                if item.get("status") == "mastered" and item.get("name")
            ],
            "knowledge_weak": [
                item["name"]
                for item in knowledge_coordinates
                if item.get("status") != "mastered" and item.get("name")
            ],
            "custom_instruction": (profile.drive_intent or {}).get(
                "custom_instruction",
                "",
            ),
        }

    async def _add_conversation_context(
        self,
        payload: dict,
        conversation_id: str,
        exclude_message_ids: set[str],
    ) -> None:
        conversation = (
            await self.db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
        ).scalar_one_or_none()
        if conversation and conversation.summary:
            payload["conversation_summary"] = conversation.summary

        statement = select(Message).where(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False,
        )
        if exclude_message_ids:
            statement = statement.where(Message.id.notin_(exclude_message_ids))
        result = await self.db.execute(
            statement
            .order_by(Message.create_time.desc(), Message.update_time.desc())
            .limit(20)
        )
        messages = list(result.scalars().all())
        messages.sort(key=message_order_key)
        payload["recent_messages"] = [
            {
                "role": item.role,
                "content": item.content or "",
                "meta": item.meta_json or {},
            }
            for item in messages
        ]
