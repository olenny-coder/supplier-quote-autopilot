from fastapi import APIRouter

from app.core.dependencies import DBSession
from app.features.chat.schema import AssistantChatRequest
from app.features.chat.schema import ChatRequest
from app.features.chat.schema import ChatResponse
from app.features.chat.schema import SendEmailRequest
from app.features.chat.schema import SendEmailResponse
from app.features.chat.service import ChatService

router = APIRouter(
    tags=["Chat"],
)


@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    payload: AssistantChatRequest,
    db: DBSession,
):
    """Site-wide procurement assistant: aware of every RFQ and carrying the
    running conversation for follow-up questions. May return a drafted supplier
    email (``pending_email``) for the buyer to confirm."""

    return await ChatService.answer_global(
        db=db,
        question=payload.question,
        history=payload.history,
    )


@router.post(
    "/chat/email/send",
    response_model=SendEmailResponse,
)
async def send_supplier_email(payload: SendEmailRequest):
    """Send a supplier email the buyer reviewed and confirmed in the chat."""

    message = await ChatService.send_supplier_email(
        to_email=payload.to_email,
        to_name=payload.to_name,
        subject=payload.subject,
        body=payload.body,
    )

    return SendEmailResponse(status="sent", message=message)


@router.post(
    "/rfqs/{rfq_id}/chat",
    response_model=ChatResponse,
)
async def chat_about_rfq(
    rfq_id: int,
    payload: ChatRequest,
    db: DBSession,
):
    answer = await ChatService.answer(
        db=db,
        rfq_id=rfq_id,
        question=payload.question,
    )

    return ChatResponse(answer=answer)
