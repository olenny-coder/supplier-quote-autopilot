"""Supplier-mail agent: composes a professional email to a supplier.

This agent does NOT send anything — it only drafts a subject + body from the
buyer's intent and the relevant RFQ/quote context. The orchestrator invokes it
when the buyer wants to contact a supplier; the actual send happens later, after
the buyer confirms, via the chat feature's mailer.
"""

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from pydantic import Field

from app.ai.llm import get_llm
from app.ai.agents.supplier_mailer.prompts import SUPPLIER_MAILER_SYSTEM_PROMPT


class DraftedEmail(BaseModel):
    """Structured output: a ready-to-send subject and body."""

    subject: str = Field(description="Short, specific subject line.")
    body: str = Field(description="Full email body as plain text.")


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm(structured_output=DraftedEmail)
    return _llm


async def draft_email(
    supplier_name: str,
    recipient_email: str,
    intent: str,
    context: str,
) -> dict:
    """Draft an email to ``supplier_name`` capturing the buyer's ``intent``.

    ``context`` is the workspace catalog (RFQs + quotes) so the draft can be
    grounded in real figures. Returns ``{"subject", "body"}``.
    """

    instruction = (
        f"Supplier: {supplier_name}\n"
        f"Recipient email: {recipient_email}\n\n"
        f"Buyer's intent for this email:\n{intent}\n\n"
        f"Relevant workspace context (RFQs and supplier quotes):\n{context}"
    )

    drafted: DraftedEmail = await _get_llm().ainvoke(
        [
            SystemMessage(content=SUPPLIER_MAILER_SYSTEM_PROMPT),
            HumanMessage(content=instruction),
        ]
    )

    return {"subject": drafted.subject, "body": drafted.body}
