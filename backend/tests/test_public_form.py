"""Public supplier form: anti-spam, link state, and ingestion edge cases.

The happy path lives in ``test_acceptance.py``. This file covers the adversarial
and boundary behaviour of the one API surface that has no authentication, which is
where the interesting failures are:

* a link that is expired, withdrawn, or simply wrong
* a bot filling the honeypot
* a client exceeding the rate limit
* a file that should not be accepted
* a resubmission that must amend rather than duplicate

Everything runs in-process through ``TestClient``, so no socket and no shared
database file is involved.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.rate_limit import get_rate_limiter
from app.features.followup.service import run_scheduler
from app.features.invitation.model import Invitation
from app.features.rfq.model import RFQ

BUYER = {
    "email": "form@acme.example.com",
    "password": "correct-horse-battery",
    "full_name": "Dana Buyer",
    "company_name": "Acme Industrial",
    "contact_email": "procurement@acme.example.com",
    "contact_phone": "+1 555 0100",
}

SUPPLIERS = [
    {
        "name": "Nova Metals",
        "contact_email": "ana@nova.example.com",
        "contact_name": "Ana Ruiz",
        "risk_rating": "low",
    },
    {
        "name": "Halcyon Fasteners",
        "contact_email": "sales@halcyon.example.com",
        "contact_name": "Ben Okafor",
        "risk_rating": "medium",
    },
]

COMPLETE_QUOTE = {
    "supplier_name": "Nova Metals",
    "contact_email": "ana@nova.example.com",
    "currency": "USD",
    "unit_price": "2.48",
    "unit": "pcs",
    "lead_time": "3 weeks",
    "moq": "500",
    "payment_terms": "Net 30",
    "incoterms": "FOB Valencia",
    "validity_date": "2027-12-31",
    "warranty_months": "12",
    "company_website": "",
}


@pytest.fixture
def buyer(client):
    """A registered buyer with a live RFQ, two invitations, and an auth header."""

    registration = client.post("/auth/register", json=BUYER)
    assert registration.status_code == 201, registration.text

    token = registration.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    rfq = client.post(
        "/rfqs",
        headers=headers,
        json={
            "item_name": "Hex Bolt M10",
            "specification": "SS304",
            "quantity": 1000,
            "unit": "pcs",
            "currency": "USD",
            "incoterms": "FOB",
            "delivery_expectation": "2026-12-01",
            "new_suppliers": SUPPLIERS,
            "send_invitations": False,
        },
    )
    assert rfq.status_code == 201, rfq.text

    body = rfq.json()
    invitations = client.get(f"/rfqs/{body['id']}/invitations", headers=headers).json()

    return {
        "headers": headers,
        "rfq_id": body["id"],
        "rfq": body,
        "invitations": invitations,
        "primary": invitations[0],
        "secondary": invitations[1],
    }


def public_path(ctx, invitation=None) -> str:
    invitation = invitation or ctx["primary"]
    return f"/public/invitations/{ctx['rfq_id']}/{invitation['token']}"


# ------------------------------------------------------------------ the preview
def test_preview_needs_no_credentials_and_leaks_nothing(client, buyer):
    response = client.get(public_path(buyer))

    assert response.status_code == 200

    body = response.json()

    # What the form needs.
    assert body["item_name"] == "Hex Bolt M10"
    assert body["buyer_company"] == "Acme Industrial"
    assert body["quantity"] == 1000
    assert body["honeypot_field"] == "company_website"
    assert body["max_upload_mb"] == settings.MAX_UPLOAD_MB

    # What it must never expose: the other suppliers, the other links, the token
    # itself, or anything about the buyer's other work.
    serialised = str(body)
    assert "Halcyon" not in serialised
    assert buyer["secondary"]["token"] not in serialised
    assert "token" not in body
    assert "supplier_id" not in body


def test_preview_counts_a_view_and_the_dashboard_sees_it(client, buyer):
    before = client.get(
        f"/rfqs/{buyer['rfq_id']}/invitations", headers=buyer["headers"]
    ).json()[0]

    assert before["view_count"] == 0
    assert before["first_viewed_at"] is None
    # Nothing has been sent yet, so "not sent" outranks "not opened" in the reason.
    assert before["status_reason"] == "The form link has not been sent yet."

    client.get(public_path(buyer))

    after = client.get(
        f"/rfqs/{buyer['rfq_id']}/invitations", headers=buyer["headers"]
    ).json()[0]

    assert after["view_count"] == 1
    assert after["first_viewed_at"] is not None


def test_opening_without_submitting_is_visible_to_the_buyer(client, buyer):
    """The distinction the follow-up engine acts on: opened, but silent."""


    client.post(f"/invitations/{buyer['primary']['id']}/resend", headers=buyer["headers"])
    client.get(public_path(buyer))
    client.get(public_path(buyer))

    invitations = client.get(
        f"/rfqs/{buyer['rfq_id']}/invitations", headers=buyer["headers"]
    ).json()

    opened = invitations[0]

    assert opened["view_count"] == 2
    assert opened["sent_at"] is not None
    assert "opened the form 2 time(s)" in opened["status_reason"]
    assert "not submitted" in opened["status_reason"]


@pytest.mark.parametrize(
    "token",
    [
        "short",
        "a" * 42,
        "not-a-real-token-but-long-enough-to-look-plausible",
    ],
)
def test_an_unknown_token_is_a_plain_404(client, buyer, token):
    response = client.get(f"/public/invitations/{buyer['rfq_id']}/{token}")

    assert response.status_code == 404
    # One message for every failure mode: the endpoint must not confirm that a
    # token exists but belongs elsewhere.
    assert response.json()["detail"] == "This quote link is not valid."


def test_a_token_from_another_rfq_is_rejected(client, buyer):
    path = f"/public/invitations/999999/{buyer['primary']['token']}"

    response = client.get(path)

    assert response.status_code == 400
    assert "does not match the request" in response.json()["detail"]


# ------------------------------------------------------------------ link state
def test_a_withdrawn_link_stops_working(client, buyer, db_session):
    cancelled = client.post(
        f"/invitations/{buyer['primary']['id']}/cancel", headers=buyer["headers"]
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    assert client.get(public_path(buyer)).status_code == 410
    assert client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE).status_code == 410


def test_an_expired_link_returns_410_with_a_usable_message(client, buyer, db_session):
    invitation = db_session.get(Invitation, buyer["primary"]["id"])
    invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    response = client.get(public_path(buyer))

    assert response.status_code == 410
    detail = response.json()["detail"]
    assert "expired" in detail.lower()
    # The supplier must be told what to do, not just that they failed.
    assert "resend" in detail.lower()

    submission = client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE)
    assert submission.status_code == 410


def test_a_past_rfq_deadline_is_visible_but_does_not_by_itself_block_submission(
    client, buyer, db_session
):
    """The deadline stops *chasing*; the link's own expiry stops *submitting*.

    A buyer who has not closed the link yet can still accept a late quote, which is
    a real and common case. Expiring the link is the buyer's decision, expressed
    through ``expires_at`` or by cancelling.
    """

    rfq = db_session.get(RFQ, buyer["rfq_id"])
    rfq.deadline = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    preview = client.get(public_path(buyer))
    assert preview.status_code == 200
    assert preview.json()["is_expired"] is False

    assert client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE).status_code == 201


def test_status_poll_reports_progress_without_counting_a_view(client, buyer):
    client.get(public_path(buyer))

    before = client.get(
        f"/rfqs/{buyer['rfq_id']}/invitations", headers=buyer["headers"]
    ).json()[0]["view_count"]

    status = client.get(f"{public_path(buyer)}/status")

    assert status.status_code == 200
    assert status.json() == {
        "status": "pending",
        "opened": True,
        "submitted": False,
        "is_expired": False,
        "expires_at": status.json()["expires_at"],
    }

    after = client.get(
        f"/rfqs/{buyer['rfq_id']}/invitations", headers=buyer["headers"]
    ).json()[0]["view_count"]

    assert after == before, "polling for status must not inflate the view count"


# ------------------------------------------------------------------- anti-spam
def test_the_honeypot_rejects_a_bot_without_saying_why(client, buyer):
    response = client.post(
        f"{public_path(buyer)}/quote",
        json={"unit_price": "0.01", "currency": "USD", "company_website": "http://spam.example"},
    )

    assert response.status_code == 400
    # A bot should not learn which check caught it.
    assert response.json()["detail"] == "Submission rejected."

    quotes = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()
    assert quotes == [], "a honeypot submission must not create a quote"


def test_the_honeypot_accepts_an_empty_value(client, buyer):
    response = client.post(
        f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE
    )

    assert response.status_code == 201


def test_the_public_endpoints_are_rate_limited(client, buyer):
    """A shared link must not be hammerable.

    The limit is per IP *and* per token. This test exhausts the per-minute window
    and asserts the refusal is a 429 carrying ``Retry-After``, which is what a
    client needs to back off correctly.
    """

    get_rate_limiter().reset()

    limit = settings.PUBLIC_RATE_LIMIT_PER_MINUTE
    path = public_path(buyer)

    responses = [client.get(path) for _ in range(limit + 5)]

    allowed = [r for r in responses if r.status_code == 200]
    limited = [r for r in responses if r.status_code == 429]

    assert len(allowed) == limit, f"expected exactly {limit} allowed, got {len(allowed)}"
    assert limited, "the limiter never fired"

    refusal = limited[0]
    assert int(refusal.headers["retry-after"]) > 0
    assert "too many" in refusal.json()["detail"].lower()


def test_the_rate_limit_covers_submission_not_only_the_preview(client, buyer):
    """A bot that never loads the form must still be stopped from submitting."""

    get_rate_limiter().reset()

    path = f"{public_path(buyer)}/quote"

    responses = [
        client.post(path, json={"unit_price": "1.00", "currency": "USD", "company_website": ""})
        for _ in range(settings.PUBLIC_RATE_LIMIT_PER_MINUTE + 5)
    ]

    assert any(r.status_code == 429 for r in responses)


# -------------------------------------------------------------------- uploads
def test_an_oversized_upload_is_refused(client, buyer):
    oversized = b"x" * ((settings.MAX_UPLOAD_MB * 1024 * 1024) + 1)

    response = client.post(
        f"{public_path(buyer)}/attachments",
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 400
    assert "larger than" in response.json()["detail"]


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("payload.html", "text/html"),
        ("script.js", "application/javascript"),
        ("noextension", "application/octet-stream"),
    ],
)
def test_disallowed_uploads_are_refused(client, buyer, filename, content_type):
    response = client.post(
        f"{public_path(buyer)}/attachments",
        files={"file": (filename, b"whatever", content_type)},
    )

    assert response.status_code == 400


def test_an_empty_upload_is_refused(client, buyer):
    response = client.post(
        f"{public_path(buyer)}/attachments",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_an_attachment_key_from_another_invitation_cannot_be_claimed(client, buyer):
    """A supplier must not be able to attach another supplier's file."""

    upload = client.post(
        f"{public_path(buyer)}/attachments",
        files={"file": ("nova.pdf", b"%PDF-1.4 nova", "application/pdf")},
    )
    assert upload.status_code == 201
    stolen_key = upload.json()["key"]

    response = client.post(
        f"{public_path(buyer, buyer['secondary'])}/quote",
        json={
            "supplier_name": "Halcyon Fasteners",
            "currency": "USD",
            "unit_price": "2.20",
            "unit": "pcs",
            "lead_time": "8 weeks",
            "company_website": "",
            "attachment_keys": [stolen_key],
        },
    )

    assert response.status_code == 400
    assert "could not be matched" in response.json()["detail"]


def test_a_valid_attachment_is_stored_on_the_quote(client, buyer):
    upload = client.post(
        f"{public_path(buyer)}/attachments",
        files={"file": ("spec.pdf", b"%PDF-1.4 spec", "application/pdf")},
    ).json()

    client.post(
        f"{public_path(buyer)}/quote",
        json={**COMPLETE_QUOTE, "attachment_keys": [upload["key"]]},
    )

    quotes = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()

    assert len(quotes[0]["attachments"]) == 1
    attachment = quotes[0]["attachments"][0]
    assert attachment["filename"] == "spec.pdf"
    assert attachment["content_type"] == "application/pdf"
    assert attachment["size"] == len(b"%PDF-1.4 spec")
    # The storage key is generated, not the uploaded name — traversal is impossible.
    assert attachment["key"].startswith("invitations/")


def test_the_attachment_url_the_api_hands_out_actually_downloads(client, buyer):
    """The URL in the quote must be fetchable, not a 404.

    Regression guard for a bug that made the feature useless in its default
    configuration: ``LocalStorage.url_for`` returns ``/files/<key>``, but the route
    serving that path refused to serve the local backend on the reasoning that local
    files are "dev only". Every attachment link the buyer clicked returned 404 — and
    local storage is what the app uses by default, so this was the normal path, not
    an edge case.
    """

    payload = b"%PDF-1.4 downloadable"
    upload = client.post(
        f"{public_path(buyer)}/attachments",
        files={"file": ("brochure.pdf", payload, "application/pdf")},
    ).json()

    client.post(
        f"{public_path(buyer)}/quote",
        json={**COMPLETE_QUOTE, "attachment_keys": [upload["key"]]},
    )

    attachment = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()[0]["attachments"][0]

    url = attachment["url"]
    path = url.split("testserver", 1)[-1] if "testserver" in url else url

    response = client.get(path)

    assert response.status_code == 200, f"{url} returned {response.status_code}"
    assert response.content == payload
    # A useful content type, not a generic blob: a browser should preview a PDF.
    assert response.headers["content-type"].startswith("application/pdf")


def test_the_file_route_does_not_serve_arbitrary_paths(client, buyer):
    """The proxy must not become a filesystem read primitive."""

    for candidate in (
        "/files/does-not-exist.pdf",
        "/files/../../../../windows/win.ini",
        "/files/invitations/../../../../etc/passwd",
    ):
        response = client.get(candidate)

        assert response.status_code in (400, 404), f"{candidate} -> {response.status_code}"


# ---------------------------------------------------------------- resubmission
def test_resubmission_amends_the_quote_rather_than_duplicating_it(client, buyer):
    first = client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE)
    assert first.status_code == 201

    partial = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Nova Metals",
            "currency": "USD",
            "unit_price": "2.30",
            "unit": "pcs",
            "lead_time": "2 weeks",
            "company_website": "",
        },
    )
    assert partial.status_code == 201

    # Same reference, one row, newest figures.
    assert partial.json()["reference_number"] == first.json()["reference_number"]
    assert partial.json()["created"] is False

    quotes = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()

    assert len(quotes) == 1
    assert quotes[0]["unit_price"] == "2.30"
    assert quotes[0]["lead_time"] == 14


def test_a_resubmission_can_complete_a_previously_incomplete_quote(client, buyer):
    partial = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Nova Metals",
            "currency": "USD",
            "unit_price": "2.30",
            "unit": "pcs",
            "company_website": "",
        },
    )
    assert partial.json()["completeness"] == "incomplete"
    assert "minimum order quantity" in partial.json()["missing_field_labels"]

    completed = client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE)

    assert completed.json()["completeness"] == "complete"
    assert completed.json()["missing_field_labels"] == []

    invitations = client.get(
        f"/rfqs/{buyer['rfq_id']}/invitations", headers=buyer["headers"]
    ).json()

    assert invitations[0]["status"] == "submitted"


def test_a_request_without_a_token_has_no_submission_path(client, buyer):
    """The token is the only credential; without it there is nothing to POST to.

    ``/public/invitations/1/quote`` happens to match the *preview* route with
    ``token="quote"``, which is GET-only — hence 405 rather than 404. Either way
    there is no way to submit without a real token, which is the property that
    matters.
    """

    assert client.post("/public/invitations/1/quote", json=COMPLETE_QUOTE).status_code in (404, 405)
    assert client.get("/public/invitations").status_code == 404
    assert client.post("/public/invitations/1/quote", json=COMPLETE_QUOTE).status_code != 201


# ----------------------------------------------------------------- full text
def test_free_text_notes_are_parsed_into_structured_fields(client, buyer):
    response = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Nova Metals",
            "currency": "USD",
            "company_website": "",
            "notes": (
                "Unit price: 2.65 USD per pc\n"
                "Lead time: 6-8 weeks\n"
                "MOQ: 750 units\n"
                "Payment terms: Net 45\n"
                "Incoterms: DDP Hamburg\n"
                "Valid until: 2027-03-15\n"
            ),
        },
    )

    assert response.status_code == 201

    quotes = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()

    quote = quotes[0]

    assert quote["unit_price"] == "2.65"
    assert quote["lead_time"] == 56, "6-8 weeks takes the upper bound"
    assert quote["moq"] == 750
    assert quote["payment_terms"] == "Net 45"
    assert quote["incoterms"] == "DDP Hamburg"
    assert quote["validity_date"] == "2027-03-15"
    assert quote["completeness"] == "complete"
    assert quote["source"] == "form"


def test_a_supplier_question_is_escalated_not_treated_as_a_quote(client, buyer, db_session):
    """A supplier waiting on the buyer must not be chased for an answer they cannot give."""

    response = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Nova Metals",
            "currency": "USD",
            "company_website": "",
            "notes": "We can quote once you confirm the target annual volume?",
        },
    )

    assert response.status_code == 201

    quotes = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()

    assert quotes[0]["blocking_question"] is not None
    assert "volume" in quotes[0]["blocking_question"].lower()
    assert any("waiting on the buyer" in flag for flag in quotes[0]["risk_flags"])

    # Backdate the sends so the reminder interval would otherwise have elapsed.
    for invitation in db_session.query(Invitation).all():
        invitation.sent_at = datetime.now(UTC) - timedelta(hours=200)
        invitation.last_sent_at = invitation.sent_at
    db_session.commit()

    summary = run_scheduler(db_session)

    escalated = [a for a in summary.actions if a.get("action") == "escalate_to_buyer"]
    assert escalated, "the blocked supplier must be surfaced to the buyer"
    assert "waiting on the buyer" in escalated[0]["reason"]

    # The blocked supplier is not chased. The second supplier, who simply never
    # responded, legitimately is — so the assertion is scoped, not global.
    assert escalated[0]["supplier"] == "Nova Metals"
    chased = {
        action.get("supplier")
        for action in summary.actions
        if action.get("result") == "awaiting_approval"
    }
    assert "Nova Metals" not in chased
    assert chased == {"Halcyon Fasteners"}


# ---------------------------------------------------------------------- config
def test_public_config_exposes_no_secrets(client):
    body = client.get("/public/config").json()

    assert body["max_upload_mb"] == settings.MAX_UPLOAD_MB
    assert body["captcha"]["provider"] == "none"
    assert body["captcha"]["site_key"] is None

    serialised = str(body).lower()
    for forbidden in ("secret", "api_key", "password", "token"):
        assert forbidden not in serialised, f"{forbidden} leaked into /public/config"
