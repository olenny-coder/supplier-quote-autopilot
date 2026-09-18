from sqlalchemy.orm import Session

from app.ai.registry import get_agent
from app.features.chat import mailer
from app.features.chat.schema import ChatMessage
from app.features.chat.schema import ChatResponse
from app.features.chat.schema import EmailDraft
from app.features.quote.service import QuoteService
from app.features.rfq.service import RFQService


class ChatService:
    """Answers procurement questions by delegating to a registered agent.

    The agent is resolved by name through the registry, so swapping in a
    different assistant — or later, an orchestrator that picks among several
    agents — does not touch this service.
    """

    AGENT_NAME = "rfq_assistant"
    GLOBAL_AGENT_NAME = "procurement_orchestrator"

    @staticmethod
    async def answer(
        db: Session,
        rfq_id: int,
        question: str,
    ) -> str:
        # Reuse existing services so RFQ-not-found raises the shared
        # NotFoundError and quotes come back in the canonical order.
        rfq = RFQService.get_by_id(db=db, rfq_id=rfq_id)
        quotes = QuoteService.get_all_for_rfq(db=db, rfq_id=rfq_id)

        agent = get_agent(ChatService.AGENT_NAME)

        return await agent(rfq, quotes, question)

    @staticmethod
    async def answer_global(
        db: Session,
        question: str,
        history: list[ChatMessage] | None = None,
    ) -> ChatResponse:
        """Answer a question about the whole workspace (every RFQ + quotes),
        carrying prior conversation turns for follow-up context.

        The orchestrator may instead return a drafted supplier email, surfaced
        as ``pending_email`` for the buyer to confirm before it is sent.
        """

        rfqs = RFQService.get_all(db=db)

        # Owning DB access here keeps the agent free of persistence concerns.
        rfqs_with_quotes = [
            (rfq, QuoteService.get_all_for_rfq(db=db, rfq_id=rfq.id))
            for rfq in rfqs
        ]

        turns = [
            {"role": m.role, "content": m.content} for m in (history or [])
        ]

        agent = get_agent(ChatService.GLOBAL_AGENT_NAME)
        result = await agent(rfqs_with_quotes, turns, question)

        pending = None
        if result.draft is not None:
            pending = EmailDraft(
                to_email=result.draft.to_email,
                to_name=result.draft.to_name,
                subject=result.draft.subject,
                body=result.draft.body,
            )

        return ChatResponse(answer=result.answer, pending_email=pending)

    @staticmethod
    async def send_supplier_email(
        to_email: str,
        to_name: str | None,
        subject: str,
        body: str,
    ) -> str:
        """Deliver a confirmed supplier email and return a buyer-facing note."""

        await mailer.send_email(to_email=to_email, subject=subject, body=body)

        recipient = f"{to_name} ({to_email})" if to_name else to_email
        return f"✅ Email sent to **{recipient}**."
