"""End-to-end acceptance test.

Walks the exact path the brief specifies, through the public HTTP API only:

    create RFQ → add 3 suppliers → unique form links → supplier submits
    → quote appears → scheduler chases the non-responder and the incomplete one
    → compare 3 quotes → recommendation → human approval

Using the API rather than the services is deliberate: it is the only way to catch
the class of bug where a service works but a router, a schema, or an auth
dependency does not.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from app.core.config import settings


def _register(client, email: str = "buyer@acme.example.com") -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery",
            "full_name": "Dana Buyer",
            "company_name": "Acme Industrial",
            "contact_email": email,
            "contact_phone": "+1 555 0100",
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_rfq(client, token: str) -> dict:
    response = client.post(
        "/rfqs",
        headers=_auth(token),
        json={
            "item_name": "Steel Bolt M10",
            "specification": "SS304, zinc plated",
            "quantity": 1000,
            "unit": "pcs",
            "currency": "USD",
            "incoterms": "FOB",
            "delivery_expectation": "2026-12-01",
            "notes": "Anti-rust coating required.",
            "new_suppliers": [
                {
                    "name": "Nova Metals",
                    "contact_email": "ana@nova.example.com",
                    "contact_name": "Ana Ruiz",
                    "country": "Spain",
                    "risk_rating": "low",
                },
                {
                    "name": "Halcyon Fasteners",
                    "contact_email": "sales@halcyon.example.com",
                    "contact_name": "Ben Okafor",
                    "country": "Vietnam",
                    "risk_rating": "medium",
                },
                {
                    "name": "Ironbridge Supply",
                    "contact_email": "quotes@ironbridge.example.com",
                    "contact_name": "Cara Lindqvist",
                    "country": "Poland",
                    "risk_rating": "high",
                },
            ],
            "send_invitations": True,
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def test_full_acceptance_flow(client, db_session):
    # ---------------------------------------------------------------- 1. buyer
    buyer = _register(client)
    token = buyer["access_token"]
    assert buyer["user"]["company_name"] == "Acme Industrial"

    # -------------------------------------------------------- 2. RFQ + 3 links
    rfq = _create_rfq(client, token)
    rfq_id = rfq["id"]

    assert rfq["invitation_count"] == 3

    invitations = client.get(
        f"/rfqs/{rfq_id}/invitations", headers=_auth(token)
    ).json()

    assert len(invitations) == 3

    tokens = {invitation["token"] for invitation in invitations}
    assert len(tokens) == 3, "each supplier must get a unique token"

    links = {invitation["form_link"] for invitation in invitations}
    assert len(links) == 3, "each supplier must get a unique form link"

    assert all(invitation["status"] == "pending" for invitation in invitations)
    assert all(invitation["sent_at"] for invitation in invitations)

    by_supplier = {invitation["supplier_name"]: invitation for invitation in invitations}

    nova = by_supplier["Nova Metals"]
    halcyon = by_supplier["Halcyon Fasteners"]
    ironbridge = by_supplier["Ironbridge Supply"]

    # ------------------------------------------------- 3. public form (no auth)
    preview = client.get(f"/public/invitations/{rfq_id}/{nova['token']}")

    assert preview.status_code == 200, preview.text

    preview_body = preview.json()
    assert preview_body["item_name"] == "Steel Bolt M10"
    assert preview_body["quantity"] == 1000
    assert preview_body["buyer_company"] == "Acme Industrial"
    assert preview_body["honeypot_field"] == "company_website"

    # ------------------------------------------------- 4. supplier A submits
    upload = client.post(
        f"/public/invitations/{rfq_id}/{nova['token']}/attachments",
        files={"file": ("nova-spec-sheet.pdf", b"%PDF-1.4 spec", "application/pdf")},
    )

    assert upload.status_code == 201, upload.text
    attachment_key = upload.json()["key"]

    submission = client.post(
        f"/public/invitations/{rfq_id}/{nova['token']}/quote",
        json={
            "supplier_name": "Nova Metals",
            "contact_email": "ana@nova.example.com",
            "currency": "USD",
            "unit_price": "2.50",
            "unit": "pcs",
            "lead_time": "3 weeks",
            "moq": "500",
            "payment_terms": "Net 30",
            "incoterms": "FOB Valencia",
            "validity_date": "2026-12-31",
            "warranty_months": "12",
            "notes": "Volume discount available above 5000 pcs.",
            "attachment_keys": [attachment_key],
        },
    )

    assert submission.status_code == 201, submission.text

    confirmation = submission.json()
    assert confirmation["reference_number"].startswith("SQ-RFQ-")
    assert confirmation["completeness"] == "complete"
    assert confirmation["lead_time_days"] == 21, "3 weeks must normalize to 21 days"

    # ------------------------------------- 5. supplier B submits incomplete
    partial = client.post(
        f"/public/invitations/{rfq_id}/{halcyon['token']}/quote",
        json={
            "supplier_name": "Halcyon Fasteners",
            "contact_email": "sales@halcyon.example.com",
            "currency": "USD",
            "unit_price": "2.20",
            "unit": "pcs",
            "lead_time": "45 days",
        },
    )

    assert partial.status_code == 201, partial.text

    partial_body = partial.json()
    assert partial_body["completeness"] == "incomplete"
    assert "minimum order quantity" in partial_body["missing_field_labels"]
    assert "payment terms" in partial_body["missing_field_labels"]

    # ------------------------------------------- 6. supplier C stays silent
    # (Ironbridge never opens the link.)

    # ------------------------------------------- 7. buyer sees the statuses
    invitations = client.get(
        f"/rfqs/{rfq_id}/invitations", headers=_auth(token)
    ).json()

    by_supplier = {invitation["supplier_name"]: invitation for invitation in invitations}

    assert by_supplier["Nova Metals"]["status"] == "submitted"
    assert by_supplier["Halcyon Fasteners"]["status"] == "incomplete"
    assert by_supplier["Ironbridge Supply"]["status"] == "pending"

    # Nova's view count shows they opened the form; Ironbridge's does not.
    assert by_supplier["Nova Metals"]["view_count"] >= 1
    assert by_supplier["Ironbridge Supply"]["view_count"] == 0

    quotes = client.get(f"/rfqs/{rfq_id}/quotes", headers=_auth(token)).json()
    assert len(quotes) == 2

    nova_quote = next(q for q in quotes if q["supplier_name"] == "Nova Metals")
    assert nova_quote["attachments"], "the uploaded spec sheet must be attached"
    assert nova_quote["normalized_total_cost"] is not None, (
        "a submitted quote must be normalized immediately so the dashboard has a "
        "landed cost without a manual comparison run"
    )

    # ------------------------------------------ 8. automated follow-up pass
    # Backdate the sends so the reminder interval has elapsed. This is what the
    # clock would do in production; manipulating time is not needed.
    from app.features.invitation.model import Invitation

    for invitation in db_session.query(Invitation).all():
        invitation.sent_at = datetime.now(UTC) - timedelta(hours=100)
        invitation.last_sent_at = invitation.sent_at

    db_session.commit()

    tick = client.post(
        "/internal/scheduler/tick",
        headers={"X-Scheduler-Secret": "test-scheduler-secret"},
    )

    assert tick.status_code == 200, tick.text

    summary = tick.json()
    # Only open invitations are scanned: Nova's complete quote is already closed out.
    assert summary["scanned"] == 2
    assert summary["auto_send_enabled"] is False

    # Two suppliers need chasing: one has not responded, one left fields blank.
    # Nova's quote is complete, so it must not be chased at all.
    chased = {action["supplier"] for action in summary["actions"]}
    assert chased == {"Halcyon Fasteners", "Ironbridge Supply"}

    kinds = {action["supplier"]: action["kind"] for action in summary["actions"]}
    assert kinds["Ironbridge Supply"] == "no_response"
    assert kinds["Halcyon Fasteners"] == "incomplete_quote"

    halcyon_action = next(
        action for action in summary["actions"] if action["supplier"] == "Halcyon Fasteners"
    )
    # Only the genuinely missing fields are requested — never the ones answered.
    assert set(halcyon_action["requested"]) == {
        "minimum order quantity",
        "payment terms",
        "delivery terms (Incoterms)",
        "quote validity date",
    }

    assert summary["queued_for_approval"] == 2
    assert summary["sent"] == 0, "AUTO_SEND_FOLLOWUPS is off, so nothing sends"

    drafts = client.get("/follow-ups?status=draft", headers=_auth(token)).json()
    assert len(drafts) == 2

    incomplete_draft = next(
        draft for draft in drafts if draft["kind"] == "incomplete_quote"
    )
    # The supplier-facing vocabulary is used, never the internal field name.
    assert "minimum order quantity" in incomplete_draft["body"].lower()
    assert "moq" not in incomplete_draft["body"].lower()

    # --------------------------------------------- 9. buyer approves the drafts
    for draft in drafts:
        approved = client.post(
            f"/follow-ups/{draft['id']}/approve",
            headers=_auth(token),
            json={},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["followup"]["status"] == "sent"

    # Re-running the scheduler must not chase anyone again.
    again = client.post(
        "/internal/scheduler/tick",
        headers={"X-Scheduler-Secret": "test-scheduler-secret"},
    ).json()

    assert again["drafted"] == 0, "a second pass must not duplicate drafts"

    # ------------------------------------------------- 10. compare the field
    # Nova raised their price to make the ranking interesting; Halcyon is cheaper
    # but incomplete and slow, so price alone must not decide it.
    quotes = client.get(f"/rfqs/{rfq_id}/quotes", headers=_auth(token)).json()
    nova_quote_id = next(q["id"] for q in quotes if q["supplier_name"] == "Nova Metals")

    client.put(
        f"/quotes/{nova_quote_id}",
        headers=_auth(token),
        json={
            "unit_price": "2.50",
            "shipping_cost": "150",
            "taxes": "75",
        },
    )

    comparison = client.post(
        f"/rfqs/{rfq_id}/comparison",
        headers=_auth(token),
        json={"use_llm": False},
    )

    assert comparison.status_code == 201, comparison.text

    body = comparison.json()
    assert body["recommended_quote_id"] is not None
    assert body["recommended_supplier"] in {"Nova Metals", "Halcyon Fasteners"}
    assert body["rationale"]
    assert body["awaiting_approval"] is True
    assert body["fx_rates"]["source"]

    ranked = [r for r in body["results"] if r["rank"] is not None]
    assert len(ranked) == 2
    assert ranked[0]["rank"] == 1

    # The ordering rule: a complete quote always ranks ahead of an incomplete one,
    # even when the incomplete one scores higher. An incomplete quote is missing
    # exactly the fields that would change its own cost and terms, so it cannot win
    # a comparison it is not fully entered into. Here Halcyon is cheaper per unit
    # and scores better, and Nova still ranks first because Nova's quote is complete.
    halcyon_result = next(
        r for r in body["results"] if r["supplier_name"] == "Halcyon Fasteners"
    )
    nova_result = next(
        r for r in body["results"] if r["supplier_name"] == "Nova Metals"
    )

    assert nova_result["completeness"] == "complete"
    assert halcyon_result["completeness"] == "incomplete"
    assert nova_result["rank"] == 1
    assert halcyon_result["rank"] == 2
    assert float(halcyon_result["total_base"]) < float(nova_result["total_base"]), (
        "the incomplete quote is genuinely cheaper, which is what makes the "
        "ordering rule meaningful rather than incidental"
    )
    assert halcyon_result["composite_score"] > nova_result["composite_score"], (
        "and it scores higher, so only the completeness rule puts it second"
    )

    # The rationale explains that ordering rather than leaving it a mystery.
    assert "lower landed cost but is incomplete" in body["rationale"]

    # The incomplete quote is docked and carries a note explaining why.
    assert halcyon_result["incompleteness_note"]

    # Nova's landed cost includes the freight and tax that were quoted separately.
    assert float(nova_result["breakdown"]["shipping"]) == 150.0
    assert float(nova_result["breakdown"]["taxes"]) == 75.0
    assert float(nova_result["total_base"]) == 2500.0 + 150.0 + 75.0

    # ------------------------------------------------------ 11. export the CSV
    export = client.get(
        f"/rfqs/{rfq_id}/comparison/export.csv", headers=_auth(token)
    )

    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert "Supplier Quote Autopilot" in export.text
    assert "Nova Metals" in export.text
    assert "Halcyon Fasteners" in export.text

    # --------------------------------------------- 12. human approval to award
    # Awarding a quote with missing fields needs an explicit override note.
    blocked = client.post(
        f"/rfqs/{rfq_id}/comparison/approve",
        headers=_auth(token),
        json={
            "quote_id": halcyon_result["quote_id"],
            "decision": "approved",
            "note": "Cheapest option, going with it.",
        },
    )
    assert blocked.status_code == 400
    assert "missing required field" in blocked.json()["detail"].lower()

    award = client.post(
        f"/rfqs/{rfq_id}/comparison/approve",
        headers=_auth(token),
        json={
            "quote_id": nova_result["quote_id"],
            "decision": "approved",
            "note": "Best combination of landing cost, lead time, and payment terms.",
        },
    )

    assert award.status_code == 201, award.text

    approval = award.json()
    assert approval["decision"] == "approved"
    assert approval["decided_by_email"] == "buyer@acme.example.com"
    assert approval["awarded_total_cost"] is not None

    updated_rfq = client.get(f"/rfqs/{rfq_id}", headers=_auth(token)).json()
    assert updated_rfq["status"] == "awarded"

    audit = client.get(f"/rfqs/{rfq_id}/approvals", headers=_auth(token)).json()
    assert len(audit) == 1

    # ------------------------------------------------------- 13. dashboard roll-up
    dashboard = client.get("/dashboard/summary", headers=_auth(token)).json()

    assert dashboard["rfqs_total"] == 1
    assert dashboard["rfqs_awarded"] == 1
    assert dashboard["suppliers_total"] == 3
    assert dashboard["invitations_total"] == 3
    assert dashboard["invitations_submitted"] == 1
    assert dashboard["invitations_incomplete"] == 1
    assert dashboard["invitations_pending"] == 1
    assert dashboard["quotes_total"] == 2
    # The communication log is complete: 3 initial form-link sends plus the 2
    # reminders the buyer approved. Nothing that went out is missing from it.
    assert dashboard["followups_sent"] == 5


def test_non_responder_is_chased_after_the_deadline_forces_expiry(client, db_session):
    """Once the deadline passes, follow-ups stop and the invitation expires."""

    buyer = _register(client, email="deadline@acme.example.com")
    token = buyer["access_token"]

    rfq = _create_rfq(client, token)
    rfq_id = rfq["id"]

    from app.features.invitation.model import Invitation

    for invitation in db_session.query(Invitation).all():
        invitation.sent_at = datetime.now(UTC) - timedelta(hours=100)
        invitation.last_sent_at = invitation.sent_at

    db_session.commit()

    first = client.post(
        "/internal/scheduler/tick",
        headers={"X-Scheduler-Secret": "test-scheduler-secret"},
    ).json()

    assert first["drafted"] == 3

    # Push the RFQ deadline into the past without changing anything else.
    from app.features.rfq.model import RFQ

    rfq_row = db_session.get(RFQ, rfq_id)
    rfq_row.deadline = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    second = client.post(
        "/internal/scheduler/tick",
        headers={"X-Scheduler-Secret": "test-scheduler-secret"},
    ).json()

    assert second["drafted"] == 0, "no chasing once the deadline has passed"
    assert second["expired"] == 3

    invitations = client.get(
        f"/rfqs/{rfq_id}/invitations", headers=_auth(token)
    ).json()

    assert all(invitation["status"] == "expired" for invitation in invitations)

    updated = client.get(f"/rfqs/{rfq_id}", headers=_auth(token)).json()
    assert updated["status"] == "closed"


def test_unauthenticated_buyer_endpoints_are_rejected(client):
    for path in ("/rfqs", "/suppliers", "/dashboard/summary", "/follow-ups"):
        response = client.get(path)
        assert response.status_code == 401, path


def test_scheduler_tick_requires_the_shared_secret(client):
    assert client.post("/internal/scheduler/tick").status_code == 403
    assert (
        client.post(
            "/internal/scheduler/tick", headers={"X-Scheduler-Secret": "wrong"}
        ).status_code
        == 403
    )


def test_ai_is_optional_everywhere(client):
    """With no LLM key configured, every AI-touching endpoint still works.

    This is the property that lets the product run on a free tier whose quota is
    spent: the deterministic paths are not a degraded mode bolted on afterwards,
    they are what the test suite exercises by default.
    """

    assert settings.llm_configured() is False

    buyer = _register(client, email="no-llm@acme.example.com")
    token = buyer["access_token"]

    rfq = _create_rfq(client, token)
    rfq_id = rfq["id"]

    invitations = client.get(
        f"/rfqs/{rfq_id}/invitations", headers=_auth(token)
    ).json()

    submission = client.post(
        f"/public/invitations/{rfq_id}/{invitations[0]['token']}/quote",
        json={
            "supplier_name": "Nova Metals",
            "unit_price": "3.10",
            "currency": "USD",
            "lead_time": "2 weeks",
            "moq": "250",
            "payment_terms": "Net 45",
            "incoterms": "EXW",
            "validity_date": "2027-01-01",
        },
    )

    assert submission.status_code == 201
    assert submission.json()["completeness"] == "complete"

    comparison = client.post(
        f"/rfqs/{rfq_id}/comparison",
        headers=_auth(token),
        json={"use_llm": True},
    )

    assert comparison.status_code == 201
    body = comparison.json()

    # The narrative falls back to the deterministic rationale, and says so.
    assert body["summary"] is None
    assert body["rationale"]
    assert body["computed_by"] == "engine"
