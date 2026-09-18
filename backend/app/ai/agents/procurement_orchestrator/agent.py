"""Procurement orchestrator: the single entry point behind the site-wide chat.

It owns the conversation and routes between two collaborating agents:

* itself — answering questions about the RFQ/quote catalog (the procurement
  knowledge), grounded in the context it is handed; and
* the supplier-mail agent — invoked through the ``DraftSupplierEmail`` tool to
  compose an email when the buyer wants to contact a supplier.

Tool calls are dispatched manually (the tool is a schema, not an executable) so
the orchestrator stays in control: a ``DraftSupplierEmail`` call produces a draft
that is returned to the UI for the buyer to confirm — nothing is sent here.
"""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from pydantic import Field

from app.ai.llm import get_llm
from app.ai.agents.procurement_assistant.agent import format_catalog
from app.ai.agents.procurement_assistant.agent import to_lc_messages
from app.ai.agents.procurement_orchestrator.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
)
from app.ai.agents.supplier_mailer import draft_email


class DraftSupplierEmail(BaseModel):
    """Prepare a draft email to a supplier for the buyer to review and confirm.

    Only call this when you already know the recipient's email address and have a
    clear purpose for the message. Do not guess the email address.
    """

    supplier_name: str = Field(
        description="Name of the supplier the email is addressed to.",
    )
    recipient_email: str = Field(
        description="The supplier's email address, provided by the buyer.",
    )
    intent: str = Field(
        description=(
            "What the buyer wants to communicate: the concern, clarification, or "
            "confirmation, including any specifics to mention."
        ),
    )


@dataclass
class EmailDraft:
    to_email: str
    to_name: str | None
    subject: str
    body: str


@dataclass
class OrchestratorResult:
    answer: str
    draft: EmailDraft | None = None


_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm().bind_tools([DraftSupplierEmail])
    return _llm


async def run(rfqs_with_quotes, history, question: str) -> OrchestratorResult:
    """Answer ``question`` or, when the buyer wants to email a supplier, return a
    draft for confirmation."""

    catalog = format_catalog(rfqs_with_quotes)
    system = f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\nCurrent workspace data:\n\n{catalog}"

    messages = [SystemMessage(content=system)]
    messages.extend(to_lc_messages(history))
    messages.append(HumanMessage(content=question))

    response = await _get_llm().ainvoke(messages)

    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        args = tool_calls[0]["args"]
        supplier_name = args.get("supplier_name", "the supplier")
        recipient_email = args.get("recipient_email", "")
        intent = args.get("intent", "")

        drafted = await draft_email(
            supplier_name=supplier_name,
            recipient_email=recipient_email,
            intent=intent,
            context=catalog,
        )

        answer = (
            f"Here's a draft email to **{supplier_name}** "
            f"(`{recipient_email}`). Review it below and choose **Send** to "
            f"deliver it, or **Cancel** to discard."
        )

        return OrchestratorResult(
            answer=answer,
            draft=EmailDraft(
                to_email=recipient_email,
                to_name=supplier_name,
                subject=drafted["subject"],
                body=drafted["body"],
            ),
        )

    return OrchestratorResult(answer=response.content)
