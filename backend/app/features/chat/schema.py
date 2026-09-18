import re
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

# Pragmatic email shape check — avoids pulling in email-validator just for this.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )


class ChatMessage(BaseModel):
    """A single prior turn in the conversation, sent back so the assistant
    keeps context across follow-up questions."""

    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=8000,
    )


class AssistantChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )

    # Earlier turns, oldest first, excluding the current question.
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=50,
    )


class EmailDraft(BaseModel):
    """A supplier email the orchestrator prepared, awaiting buyer confirmation."""

    to_email: str
    to_name: str | None = None
    subject: str
    body: str


class ChatResponse(BaseModel):
    answer: str

    # Present when the assistant has drafted a supplier email for confirmation.
    pending_email: EmailDraft | None = None


class SendEmailRequest(BaseModel):
    to_email: str = Field(max_length=320)
    to_name: str | None = Field(default=None, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("to_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("to_email must be a valid email address")
        return v


class SendEmailResponse(BaseModel):
    status: Literal["sent"]
    message: str
