"""RFQ assistant: a minimal single agent that answers natural-language
questions about one RFQ and its supplier quotes.

This is intentionally small — it's the first conversational agent and the
proof that the ``app/ai`` seam supports more than the extraction graph. Future
work (tools, multi-step reasoning, orchestration across agents) builds on the
same registry entry.
"""

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

from app.ai.llm import get_llm
from app.ai.agents.rfq_assistant.prompts import RFQ_ASSISTANT_SYSTEM_PROMPT

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


def _format_context(rfq, quotes) -> str:
    lines = [
        "RFQ:",
        f"- Item: {rfq.item_name}",
        f"- Specification: {rfq.specification}",
        f"- Quantity: {rfq.quantity}",
        f"- Delivery expectation: {rfq.delivery_expectation}",
        f"- Notes: {rfq.notes or '—'}",
        "",
        "Supplier quotes:",
    ]

    if not quotes:
        lines.append("- (no quotes yet)")
    else:
        for q in quotes:
            total = q.unit_price * rfq.quantity
            lines.append(
                f"- {q.supplier_name}: unit {q.unit_price} {q.currency}, "
                f"total {total} {q.currency}, lead {q.lead_time} days, "
                f"terms {q.payment_terms or '—'}, remarks {q.remarks or '—'}"
            )

    return "\n".join(lines)


async def answer_question(rfq, quotes, question: str) -> str:
    """Answer ``question`` about the given RFQ and its quotes."""

    context = _format_context(rfq, quotes)

    response = await _get_llm().ainvoke(
        [
            SystemMessage(content=RFQ_ASSISTANT_SYSTEM_PROMPT),
            HumanMessage(content=f"{context}\n\nQuestion: {question}"),
        ]
    )

    return response.content
