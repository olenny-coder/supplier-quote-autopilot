"""Agent registry — the single place agents are registered and resolved.

Today it holds one conversational agent. It's the seed for orchestration:
as more agents are added, callers (and a future orchestrator) discover and
route to them by name through ``get_agent`` instead of importing each agent
module directly.
"""

from collections.abc import Callable

from app.ai.agents.procurement_assistant import (
    answer_question as procurement_answer_question,
)
from app.ai.agents.procurement_orchestrator import run as orchestrator_run
from app.ai.agents.rfq_assistant import answer_question as rfq_answer_question
from app.ai.agents.supplier_mailer import draft_email as supplier_draft_email

# name -> agent entry point (callable)
AGENTS: dict[str, Callable] = {
    "rfq_assistant": rfq_answer_question,
    "procurement_assistant": procurement_answer_question,
    "procurement_orchestrator": orchestrator_run,
    "supplier_mailer": supplier_draft_email,
}


def get_agent(name: str) -> Callable:
    """Resolve a registered agent by name.

    Raises:
        KeyError: if no agent is registered under ``name``.
    """

    if name not in AGENTS:
        raise KeyError(f"Unknown agent: {name!r}")

    return AGENTS[name]


def available_agents() -> list[str]:
    return list(AGENTS)
