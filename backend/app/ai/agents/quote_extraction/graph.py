"""Quote-extraction agent: a LangGraph graph that reads a supplier-quote PDF
and returns structured quotes via the vision-capable LLM."""

import base64

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from app.ai.llm import get_llm
from app.ai.agents.quote_extraction.prompts import (
    QUOTE_EXTRACTION_SYSTEM_PROMPT,
)
from app.ai.agents.quote_extraction.schemas import ExtractedQuotes
from app.ai.agents.quote_extraction.state import QuoteExtractionState

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = get_llm(structured_output=ExtractedQuotes)
    return _llm


async def extract_quotes(
    state: QuoteExtractionState,
) -> QuoteExtractionState:
    encoded_pdf = base64.b64encode(state["pdf_bytes"]).decode("utf-8")

    result = await _get_llm().ainvoke(
        [
            SystemMessage(content=QUOTE_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {
                        "type": "file",
                        "source_type": "base64",
                        "mime_type": "application/pdf",
                        "data": encoded_pdf,
                    },
                ]
            ),
        ]
    )

    return {
        **state,
        "extracted_quotes": result,
    }


builder = StateGraph(QuoteExtractionState)
builder.add_node("extract_quotes", extract_quotes)
builder.add_edge(START, "extract_quotes")
builder.add_edge("extract_quotes", END)

quote_extraction_graph = builder.compile()
