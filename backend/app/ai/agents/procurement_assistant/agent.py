"""Procurement assistant: a site-wide conversational agent.

Unlike ``rfq_assistant`` (scoped to a single RFQ), this agent answers questions
about the entire workspace — every RFQ and its supplier quotes — and carries the
running conversation so follow-up questions keep their context.

The data is gathered by the chat service (which owns DB access) and handed in as
``(rfq, quotes)`` pairs; this module only turns that into a prompt and calls the
LLM, mirroring the split used by the rest of ``app/ai``.
"""

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from app.ai.llm import get_llm
from app.ai.agents.procurement_assistant.prompts import (
    PROCUREMENT_ASSISTANT_SYSTEM_PROMPT,
)

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


def format_catalog(rfqs_with_quotes) -> str:
    """Render every RFQ and its quotes into a compact, grounded digest."""

    if not rfqs_with_quotes:
        return "There are no RFQs in the workspace yet."

    blocks = []
    for rfq, quotes in rfqs_with_quotes:
        lines = [
            f"RFQ #{rfq.id}: {rfq.item_name}",
            f"  Specification: {rfq.specification}",
            f"  Quantity: {rfq.quantity}",
            f"  Delivery expectation: {rfq.delivery_expectation}",
            f"  Notes: {rfq.notes or '—'}",
        ]

        if not quotes:
            lines.append("  Quotes: (none yet)")
        else:
            lines.append("  Quotes (cheapest unit price first):")
            for q in quotes:
                total = q.unit_price * rfq.quantity
                lines.append(
                    f"    - {q.supplier_name}: unit {q.unit_price} {q.currency}, "
                    f"total {total} {q.currency}, lead {q.lead_time} days, "
                    f"terms {q.payment_terms or '—'}, remarks {q.remarks or '—'}"
                )

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def to_lc_messages(history):
    """Convert prior turns ({"role", "content"}) into LangChain messages."""

    messages = []
    for turn in history:
        role = turn.get("role")
        content = turn.get("content", "")
        if not content:
            continue
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


async def answer_question(rfqs_with_quotes, history, question: str) -> str:
    """Answer ``question`` using the full RFQ catalog and prior conversation."""

    catalog = format_catalog(rfqs_with_quotes)
    system = (
        f"{PROCUREMENT_ASSISTANT_SYSTEM_PROMPT}\n\n"
        f"Current workspace data:\n\n{catalog}"
    )

    messages = [SystemMessage(content=system)]
    messages.extend(to_lc_messages(history))
    messages.append(HumanMessage(content=question))

    response = await _get_llm().ainvoke(messages)

    return response.content
