from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ProfileInitializeRequest(BaseModel):
    course_id: str
    answers: Optional[Dict[str, Any]] = None

class ProfileDialogueUpdateRequest(BaseModel):
    course_id: str
    message: str = Field(..., min_length=1, max_length=1000)

class ProfileGoalUpdateRequest(BaseModel):
    course_id: str
    learning_goal: str = Field(..., min_length=1, max_length=200)

class ProfileInstructionUpdateRequest(BaseModel):
    course_id: str
    custom_instruction: str = Field(..., min_length=0, max_length=1000)
