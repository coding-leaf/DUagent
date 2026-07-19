import mimetypes
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.services.agent_client import AgentClient, AgentServiceError, agent_client


class TutoringArtifactNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TutoringArtifact:
    filename: str
    media_type: str
    content: bytes


class TutoringArtifactService:
    def __init__(self, db: AsyncSession, client: AgentClient | None = None) -> None:
        self.db = db
        self.client = client or agent_client

    async def download(
        self,
        *,
        user_id: str,
        conversation_id: str,
        filename: str,
    ) -> TutoringArtifact:
        conversation = await self.db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.is_deleted == False,
            )
        )
        if conversation is None:
            raise TutoringArtifactNotFoundError

        try:
            content = await self.client.get_bytes(
                "/agent/v2/workbench/artifacts",
                {
                    "user_id": user_id,
                    "course_id": conversation.course_id,
                    "conversation_id": conversation_id,
                    "filename": filename,
                },
            )
        except AgentServiceError as exc:
            if exc.status_code == 404:
                raise TutoringArtifactNotFoundError from exc
            raise

        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return TutoringArtifact(filename, media_type, content)
