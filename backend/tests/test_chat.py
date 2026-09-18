from datetime import date

import pytest

from app.ai.agents import procurement_orchestrator
from app.ai.agents import supplier_mailer
from app.ai.agents.supplier_mailer.agent import DraftedEmail
from app.ai.registry import available_agents, get_agent
from app.core.exceptions import NotFoundError
from app.features.chat.schema import ChatMessage
from app.features.chat.service import ChatService
from app.features.quote.schema import QuoteCreate
from app.features.quote.service import QuoteService
from app.features.rfq.schema import RFQCreate
from app.features.rfq.service import RFQService


def test_registry_resolves_rfq_assistant():
    agent = get_agent("rfq_assistant")
    assert callable(agent)
    assert "rfq_assistant" in available_agents()


def test_registry_resolves_procurement_assistant():
    agent = get_agent("procurement_assistant")
    assert callable(agent)
    assert "procurement_assistant" in available_agents()


def test_registry_unknown_agent_raises():
    with pytest.raises(KeyError):
        get_agent("does_not_exist")


async def test_chat_missing_rfq_raises_not_found(db_session):
    # The RFQ lookup happens before any LLM call, so this needs no API key.
    with pytest.raises(NotFoundError):
        await ChatService.answer(
            db=db_session,
            rfq_id=999,
            question="Which supplier is cheapest?",
        )


class _FakeResponse:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeLLM:
    """Captures the messages an agent would send instead of calling OpenAI."""

    def __init__(self, response=None):
        self.last_messages = None
        self._response = response or _FakeResponse("ok")

    async def ainvoke(self, messages):
        self.last_messages = messages
        return self._response


def _seed_steel_bolt_rfq(db_session):
    rfq = RFQService.create(
        db=db_session,
        payload=RFQCreate(
            item_name="Steel Bolt M10",
            specification="SS304",
            quantity=100,
            delivery_expectation=date(2026, 7, 15),
        ),
    )
    QuoteService.create(
        db=db_session,
        rfq_id=rfq.id,
        payload=QuoteCreate(
            supplier_name="Acme",
            unit_price=2,
            currency="USD",
            lead_time=7,
        ),
    )
    return rfq


async def test_answer_global_grounds_on_all_rfqs_and_history(
    db_session, monkeypatch
):
    _seed_steel_bolt_rfq(db_session)

    fake = _FakeLLM()
    monkeypatch.setattr(procurement_orchestrator.agent, "_get_llm", lambda: fake)

    response = await ChatService.answer_global(
        db=db_session,
        question="Who is cheapest?",
        history=[ChatMessage(role="user", content="earlier turn")],
    )

    # Plain Q&A: the orchestrator answers and drafts no email.
    assert response.answer == "ok"
    assert response.pending_email is None

    # System prompt carries the workspace catalog; the question and prior turn
    # both reach the model.
    system, *rest = fake.last_messages
    assert "Steel Bolt M10" in system.content
    assert "Acme" in system.content
    contents = [m.content for m in rest]
    assert "earlier turn" in contents
    assert "Who is cheapest?" in contents


async def test_answer_global_returns_pending_email_on_tool_call(
    db_session, monkeypatch
):
    _seed_steel_bolt_rfq(db_session)

    # Orchestrator decides to email a supplier -> emits a tool call.
    tool_call = {
        "name": "DraftSupplierEmail",
        "args": {
            "supplier_name": "Acme",
            "recipient_email": "sales@acme.com",
            "intent": "Ask whether the 7-day lead time can be shortened.",
        },
        "id": "call_1",
    }
    orchestrator_llm = _FakeLLM(_FakeResponse("", tool_calls=[tool_call]))
    monkeypatch.setattr(
        procurement_orchestrator.agent, "_get_llm", lambda: orchestrator_llm
    )

    # The mail agent composes the draft (structured output).
    mailer_llm = _FakeLLM(
        DraftedEmail(subject="Lead time on Steel Bolt M10", body="Hello Acme, ...")
    )
    monkeypatch.setattr(supplier_mailer.agent, "_get_llm", lambda: mailer_llm)

    response = await ChatService.answer_global(
        db=db_session,
        question="Email Acme at sales@acme.com about their lead time.",
    )

    assert response.pending_email is not None
    assert response.pending_email.to_email == "sales@acme.com"
    assert response.pending_email.to_name == "Acme"
    assert response.pending_email.subject == "Lead time on Steel Bolt M10"
    assert "Acme" in response.pending_email.body
