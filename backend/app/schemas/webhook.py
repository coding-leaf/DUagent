from typing import Optional

from pydantic import BaseModel


class AgentWebhookRequest(BaseModel):
    task_id: str
    task_type: str
    status: str
    result: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
