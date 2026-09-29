"""The workspace audit log — what gets recorded, and what the buyer can download.

Two claims are under test, and they are different claims.

**Completeness.** The log is only worth building if the actions a buyer would need
to account for actually appear in it, attributed to the right actor, in the order
they happened. So the fixture below drives the whole workflow through the public
HTTP API — register, create an RFQ, invite two suppliers, one submits through the
tokenized form, the comparison runs, the award is approved — and the assertions
then walk the log that came out. Going through HTTP matters: a service can log
correctly while a router never calls it, and that is invisible from a unit test.

**Integrity.** An audit trail is a claim about what happened, so the things that
would make it lie are tested directly: a row cannot be updated, there is no
endpoint that writes or deletes one, one tenant cannot see another's, and an entry
about a deleted RFQ keeps the reference it needs to stay readable. The last one is
why ``rfq_id`` is a plain integer with snapshots beside it rather than a foreign
key — the test deletes the RFQ and then reads the history back.
"""

import csv
import io
from datetime import date
from datetime import timedelta

import pytest
from sqlalchemy.exc import InvalidRequestError

from app.core.mixins import utcnow
from app.features.audit.model import AuditEntry
from app.features.audit.service import AuditService
from app.main import app

BUYER = {
    "email": "audit@marina-fm.example.com",
    "password": "correct-horse-battery",
    "full_name": "Dana Whitfield",
    "company_name": "Marina Facilities Management Pte Ltd",
    "contact_email": "procurement@marina-fm.example.com",
}

OTHER_BUYER = {
    "email": "other@harbourworks.example.com",
    "password": "correct-horse-battery",
    "full_name": "Alex Tan",
    "company_name": "Harbour Works Pte Ltd",
}

SUPPLIERS = [
    {
        "name": "Sin Heng M&E Pte Ltd",
        "contact_email": "kelvin@sinheng.example.com",
        "contact_name": "Kelvin Tan",
    },
    {
        "name": "Teck Guan Facilities Services Pte Ltd",
        "contact_email": "serena@teckguan.example.com",
        "contact_name": "Serena Lim",
    },
]

QUOTE = {
    "supplier_name": "Teck Guan Facilities Services Pte Ltd",
    "currency": "SGD",
    "unit_price": "162.00",
    "unit": "per point",
    "response_time_hours": "2",
    "compliance_accreditations": [],
    "gst_rate": "9",
    "payment_terms": "Net 30",
    "validity_date": (date.today() + timedelta(days=300)).isoformat(),
    "company_website": "",
}

RFQ_PAYLOAD = {
    "item_name": "Corridor lighting replacement — Block C",
    "specification": "24 nos. LED fittings, circuit tested.",
    "category": "Electrical Minor Works",
    "quantity": 24,
    "unit": "per point",
    "currency": "SGD",
    "gst_rate": 9,
    "delivery_expectation": (date.today() + timedelta(days=45)).isoformat(),
    "deadline": (utcnow() + timedelta(days=10)).isoformat(),
    "required_response_hours": 4,
    "notes": "Photographs required.",
    "new_suppliers": SUPPLIERS,
    "send_invitations": False,
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client, payload: dict) -> dict:
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201, response.text

    return _auth(response.json()["access_token"])


@pytest.fixture
def workspace(client):
    """A buyer who has done everything the log is supposed to remember."""

    headers = _register(client, BUYER)

    rfq = client.post("/rfqs", headers=headers, json=RFQ_PAYLOAD)

    assert rfq.status_code == 201, rfq.text

    rfq_id = rfq.json()["id"]

    invitations = client.get(f"/rfqs/{rfq_id}/invitations", headers=headers).json()

    primary = invitations[0]

    submitted = client.post(
        f"/public/invitations/{rfq_id}/{primary['token']}/quote",
        json=QUOTE,
    )

    assert submitted.status_code == 201, submitted.text

    # The submission response deliberately carries no internal id — the supplier
    # gets a reference number and nothing else — so the buyer's own quote list is
    # where the id for the award comes from.
    quotes = client.get(f"/rfqs/{rfq_id}/quotes", headers=headers).json()

    assert len(quotes) == 1, quotes

    quote_id = quotes[0]["id"]

    comparison = client.post(
        f"/rfqs/{rfq_id}/comparison",
        headers=headers,
        json={"use_llm": False},
    )

    assert comparison.status_code == 201, comparison.text

    approval = client.post(
        f"/rfqs/{rfq_id}/comparison/approve",
        headers=headers,
        json={
            "quote_id": quote_id,
            "decision": "approved",
            "note": "Lowest landed cost with a 2-hour SLA.",
        },
    )

    assert approval.status_code == 201, approval.text

    return {
        "headers": headers,
        "rfq_id": rfq_id,
        "rfq_number": rfq.json()["rfq_number"],
        "invitations": invitations,
        "quote": quotes[0],
        "quote_id": quote_id,
    }


def _log(client, headers, **params) -> dict:
    response = client.get("/audit", headers=headers, params=params)

    assert response.status_code == 200, response.text

    return response.json()


def _actions(body: dict) -> list[str]:
    return [entry["action"] for entry in body["entries"]]


# ================================================================ completeness
def test_the_whole_workflow_lands_in_the_log(client, workspace):
    body = _log(client, workspace["headers"], limit=200)

    actions = _actions(body)

    # The workflow, newest first: the award is the last thing that happened.
    for expected in (
        "rfq.created",
        "supplier.created",
        "invitation.created",
        "quote.submitted",
        "comparison.run",
        "award.approved",
    ):
        assert expected in actions, f"{expected} missing from {actions}"

    assert actions[0] == "award.approved"
    assert actions[-1] == "rfq.created"


def test_the_award_entry_carries_the_buyers_own_words(client, workspace):
    entry = next(
        item
        for item in _log(client, workspace["headers"])["entries"]
        if item["action"] == "award.approved"
    )

    assert entry["actor_type"] == "buyer"
    assert entry["actor_label"] == BUYER["company_name"]
    assert "Lowest landed cost with a 2-hour SLA." in entry["summary"]
    assert entry["detail"]["decision"] == "approved"
    assert entry["detail"]["supplier_name"] == QUOTE["supplier_name"]
    assert entry["rfq_number"] == workspace["rfq_number"]


def test_a_supplier_submission_is_attributed_to_the_supplier(client, workspace):
    """The one entry in the log that the workspace owner did not cause."""

    entry = next(
        item
        for item in _log(client, workspace["headers"])["entries"]
        if item["action"] == "quote.submitted"
    )

    # The actor is the supplier the buyer invited — the holder of the link that was
    # used — not the name typed into the form. A subcontractor answering on someone
    # else's link is exactly the case where the two differ, and the log has to say
    # who was actually asked, with what they wrote kept beside it.
    assert entry["actor_type"] == "supplier"
    assert entry["actor_label"] == workspace["invitations"][0]["supplier_name"]

    assert entry["detail"]["supplier_name"] == QUOTE["supplier_name"] != entry["actor_label"]

    assert entry["entity_type"] == "quote"
    assert entry["detail"]["completeness"] == "complete"


def test_creating_an_rfq_records_the_numbers_it_was_created_with(client, workspace):
    entry = next(
        item
        for item in _log(client, workspace["headers"])["entries"]
        if item["action"] == "rfq.created"
    )

    assert entry["detail"]["quantity"] == 24
    assert entry["detail"]["unit"] == "per point"
    assert entry["detail"]["currency"] == "SGD"


def test_the_bulk_invite_is_one_entry_naming_every_supplier(client, workspace):
    """Twelve contractors is one action by the buyer, not twelve log lines."""

    entries = [
        item
        for item in _log(client, workspace["headers"])["entries"]
        if item["action"] == "invitation.created" and item["entity_id"] is None
    ]

    assert len(entries) == 1

    entry = entries[0]

    assert entry["detail"]["count"] == 2
    assert set(entry["detail"]["suppliers"]) == {s["name"] for s in SUPPLIERS}
    for supplier in SUPPLIERS:
        assert supplier["name"] in entry["summary"]


def test_an_edit_records_the_fields_that_changed(client, workspace):
    response = client.put(
        f"/rfqs/{workspace['rfq_id']}",
        headers=workspace["headers"],
        json={"item_name": "Corridor lighting replacement — Block C (revised)"},
    )

    assert response.status_code == 200, response.text

    entry = next(
        item
        for item in _log(client, workspace["headers"])["entries"]
        if item["action"] == "rfq.updated"
    )

    assert entry["detail"]["changed"]["item_name"]["to"].endswith("(revised)")
    assert entry["detail"]["changed"]["item_name"]["from"] != entry["detail"]["changed"]["item_name"]["to"]
    # A change list is not a second copy of the RFQ: only what moved is in it.
    assert set(entry["detail"]["changed"]) == {"item_name"}


def test_reading_the_comparison_page_does_not_write_a_log_line(client, workspace):
    """The log records changes and outbound messages, never views."""

    before = _log(client, workspace["headers"], limit=200)["total"]

    client.get(f"/rfqs/{workspace['rfq_id']}/comparison", headers=workspace["headers"])
    client.get(f"/rfqs/{workspace['rfq_id']}/comparison", headers=workspace["headers"])

    assert _log(client, workspace["headers"], limit=200)["total"] == before


def test_the_schedulers_own_actions_are_in_the_log(client, workspace, db_session):
    """The headline claim: automatic chasing leaves a trace.

    This is the part no screen can show. The reminder is written by the scheduler
    inside the web process, attributed to nobody in the workspace, because no person
    did it — and without that entry the buyer's only evidence of having chased a
    supplier would be the supplier's word.
    """

    from app.core.mixins import utcnow as _now
    from app.features.followup.service import run_scheduler

    # The fixture invites without sending, and the policy does not chase an
    # invitation that was never emailed — so send it first, exactly as the buyer's
    # "Resend link" action does. The *second* supplier is the one who never answered;
    # the first has already submitted.
    invitation_id = workspace["invitations"][1]["id"]

    sent = client.post(
        f"/invitations/{invitation_id}/resend", headers=workspace["headers"]
    )

    assert sent.status_code in (200, 201), sent.text

    # Then drive the sweep to a point where the first reminder interval (72h by
    # default) has elapsed but the RFQ deadline (10 days out) has not — otherwise
    # the expiry pass runs first and marks the invitation terminal, which is a
    # different branch.
    run_scheduler(db_session, now=_now() + timedelta(days=4))

    entries = _log(client, workspace["headers"], limit=200)["entries"]

    automatic = [entry for entry in entries if entry["actor_type"] == "system"]

    assert automatic, "the scheduler left no trace in the audit log"
    assert {entry["actor_label"] for entry in automatic} == {"Scheduler"}
    assert "followup.drafted" in {entry["action"] for entry in automatic}

    drafted = next(
        entry for entry in automatic if entry["action"] == "followup.drafted"
    )

    assert drafted["detail"]["status"] == "draft"  # AUTO_SEND_FOLLOWUPS is off
    assert drafted["rfq_number"] == workspace["rfq_number"]

    # And the other automatic branch: past the deadline, the invitation expires and
    # the RFQ closes. Both are state changes a buyer has to be able to account for,
    # and neither appears anywhere else in the product.
    #
    # The close pass only touches RFQs that are still `open`, and the fixture's RFQ
    # was awarded earlier, so this needs a second one that nobody awarded. It needs
    # an invitation too: the close pass runs in the same block as the expiry pass.
    directory = client.get("/suppliers", headers=workspace["headers"]).json()

    second = client.post(
        "/rfqs",
        headers=workspace["headers"],
        json={
            **RFQ_PAYLOAD,
            "item_name": "Second RFQ with a deadline nobody met",
            "new_suppliers": [],
            "supplier_ids": [directory[0]["id"]],
        },
    )

    assert second.status_code == 201, second.text

    run_scheduler(db_session, now=_now() + timedelta(days=20))

    actions = _actions(_log(client, workspace["headers"], limit=200))

    assert "invitation.expired" in actions
    assert "rfq.closed" in actions


def test_a_manual_quote_and_its_deletion_are_both_recorded(client, workspace):
    created = client.post(
        f"/rfqs/{workspace['rfq_id']}/quotes",
        headers=workspace["headers"],
        json={
            "supplier_name": "Lian Aik Building Services Pte Ltd",
            "currency": "SGD",
            "unit_price": "150.00",
            "unit": "per point",
        },
    )

    assert created.status_code == 201, created.text

    quote_id = created.json()["id"]

    assert _actions(_log(client, workspace["headers"]))[0] == "quote.recorded"

    deleted = client.delete(f"/quotes/{quote_id}", headers=workspace["headers"])

    assert deleted.status_code == 204

    entries = _log(client, workspace["headers"])["entries"]

    assert entries[0]["action"] == "quote.deleted"
    assert entries[0]["detail"]["supplier_name"] == "Lian Aik Building Services Pte Ltd"
    assert entries[0]["detail"]["unit_price"] == "148.0000" or entries[0]["detail"]["unit_price"].startswith("150")


def test_the_filters_offer_only_what_this_workspace_has_done(client, workspace):
    body = _log(client, workspace["headers"])

    offered = {option["action"] for option in body["available_actions"]}

    assert "award.approved" in offered
    assert "followup.sent" not in offered  # nothing has been chased here

    assert [option["rfq_id"] for option in body["available_rfqs"]] == [
        workspace["rfq_id"]
    ]


# ==================================================================== filtering
def test_entries_can_be_filtered_by_action_and_actor(client, workspace):
    only_awards = _log(client, workspace["headers"], action="award.approved")

    assert _actions(only_awards) == ["award.approved"]

    only_supplier = _log(client, workspace["headers"], actor_type="supplier")

    assert {entry["actor_type"] for entry in only_supplier["entries"]} == {"supplier"}
    assert only_supplier["total"] >= 1


def test_an_unknown_filter_value_is_rejected_rather_than_returning_nothing(
    client, workspace
):
    """An empty audit page reads as "nothing happened" — the worst wrong answer."""

    response = client.get(
        "/audit", headers=workspace["headers"], params={"action": "rfq.banana"}
    )

    assert response.status_code == 400
    assert "rfq.banana" in response.json()["detail"]


def test_paging_reports_the_total_not_just_the_page(client, workspace):
    first = _log(client, workspace["headers"], limit=2, offset=0)
    second = _log(client, workspace["headers"], limit=2, offset=2)

    assert len(first["entries"]) == 2
    assert first["limit"] == 2
    assert first["total"] == second["total"]

    ids = {entry["id"] for entry in first["entries"]}

    assert not ids & {entry["id"] for entry in second["entries"]}


def test_entries_are_newest_first(client, workspace):
    entries = _log(client, workspace["headers"], limit=200)["entries"]

    ordering = [(entry["created_at"], entry["id"]) for entry in entries]

    assert ordering == sorted(ordering, reverse=True)


# ==================================================================== integrity
def test_the_endpoints_require_a_token(client, workspace):
    assert client.get("/audit").status_code == 401
    assert client.get("/audit/export.csv").status_code == 401


def test_there_is_no_way_to_write_or_delete_a_log_entry():
    """Not "we don't call it" — the published API has no such verb.

    Read from the OpenAPI schema rather than by walking ``app.routes``: this
    FastAPI version keeps included routers as opaque objects, so attribute-walking
    silently returns nothing and the assertion would pass over an empty set.
    """

    paths = app.openapi()["paths"]

    audit_paths = {path: methods for path, methods in paths.items() if "audit" in path}

    assert set(audit_paths) == {"/audit", "/audit/export.csv"}

    for path, operations in audit_paths.items():
        assert set(operations) == {"get"}, f"{path} exposes {sorted(operations)}"


def test_an_entry_cannot_be_updated(db_session, workspace, client):
    """History is append-only, enforced by a listener rather than by convention."""

    entry = db_session.query(AuditEntry).first()

    assert entry is not None

    entry.summary = "rewritten"

    with pytest.raises((RuntimeError, InvalidRequestError)) as excinfo:
        db_session.commit()

    assert "append-only" in str(excinfo.value)

    db_session.rollback()


def test_one_tenant_cannot_see_another_tenants_log(client, workspace):
    other_headers = _register(client, OTHER_BUYER)

    body = _log(client, other_headers)

    assert body["entries"] == []
    assert body["total"] == 0
    # Their account exists, so the log is empty rather than missing.
    assert body["available_actions"] == []


def test_the_log_survives_the_rfq_it_describes(client, workspace):
    """The entry that records the deletion is the one that has to outlive it."""

    deleted = client.delete(
        f"/rfqs/{workspace['rfq_id']}", headers=workspace["headers"]
    )

    assert deleted.status_code == 204

    body = _log(client, workspace["headers"], limit=200)

    actions = _actions(body)

    assert "rfq.deleted" in actions
    # Everything that happened to it is still there...
    assert "quote.submitted" in actions
    assert "award.approved" in actions

    deletion = next(item for item in body["entries"] if item["action"] == "rfq.deleted")

    # ...and still says which RFQ it was, which is the whole point of the snapshot.
    assert deletion["rfq_number"] == workspace["rfq_number"]
    assert "Corridor lighting" in deletion["item_name"]

    # The history stays filterable by the id it belonged to, because that column is
    # a stored reference rather than a foreign key that another delete can clear.
    filtered = _log(client, workspace["headers"], rfq_id=workspace["rfq_id"])

    scoped = [
        entry for entry in body["entries"] if entry["rfq_id"] == workspace["rfq_id"]
    ]

    # Everything filed against this RFQ comes back — including the deletion — and
    # the directory entries from the same session, which belong to no RFQ, do not.
    assert filtered["total"] == len(scoped) > 0
    assert len(scoped) < body["total"]
    assert all(
        entry["rfq_number"] == workspace["rfq_number"]
        for entry in filtered["entries"]
    )
    assert "rfq.deleted" in _actions(filtered)
    assert filtered["available_rfqs"][0]["rfq_number"] == workspace["rfq_number"]


def test_recording_without_a_workspace_is_a_no_op(db_session):
    """The seed script runs before any account exists; that must not raise."""

    assert (
        AuditService.record(
            db_session,
            user_id=None,
            action="rfq.created",
            entity_type="rfq",
            summary="No workspace behind this.",
        )
        is None
    )


def test_a_percent_in_a_summary_cannot_break_the_log(client, workspace):
    """Supplementary: the detail column round-trips, whatever the text contains."""

    response = client.put(
        f"/rfqs/{workspace['rfq_id']}",
        headers=workspace["headers"],
        json={"item_name": 'Tiles 60% "grade", 300x300'},
    )

    assert response.status_code == 200, response.text

    entry = next(
        item
        for item in _log(client, workspace["headers"])["entries"]
        if item["action"] == "rfq.updated"
    )

    assert entry["detail"]["changed"]["item_name"]["to"] == 'Tiles 60% "grade", 300x300'


# ==================================================================== the export
def test_the_csv_download_has_the_headers_a_browser_needs(client, workspace):
    response = client.get("/audit/export.csv", headers=workspace["headers"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert ".csv" in response.headers["content-disposition"]


def test_the_csv_names_the_workspace_and_the_filters_applied(client, workspace):
    text = client.get("/audit/export.csv", headers=workspace["headers"]).text

    assert "Supplier Quote Autopilot — audit log export" in text
    assert BUYER["company_name"] in text
    assert "action=all" in text


def test_the_csv_has_one_row_per_entry_oldest_first(client, workspace):
    text = client.get("/audit/export.csv", headers=workspace["headers"]).text

    rows = list(csv.reader(io.StringIO(text)))

    header_index = rows.index(
        [row for row in rows if row and row[0] == "Timestamp (UTC)"][0]
    )
    header = rows[header_index]

    assert header == [
        "Timestamp (UTC)",
        "Action",
        "Action code",
        "Actor",
        "Actor type",
        "RFQ number",
        "Item",
        "Entity",
        "Entity ID",
        "Summary",
        "Detail",
    ]

    data = [row for row in rows[header_index + 1 :] if len(row) == len(header)]

    assert len(data) == _log(client, workspace["headers"], limit=500)["total"]
    assert data[0][2] == "rfq.created"
    assert data[-1][2] == "award.approved"

    # Human label in one column, stable code in the next: a spreadsheet reader wants
    # the first and a script wants the second.
    assert data[0][1] == "RFQ created"


def test_the_csv_honours_the_same_filters_as_the_page(client, workspace):
    text = client.get(
        "/audit/export.csv",
        headers=workspace["headers"],
        params={"action": "award.approved"},
    ).text

    rows = [
        row
        for row in csv.reader(io.StringIO(text))
        if len(row) == 11 and row[2] == "award.approved"
    ]

    assert len(rows) == 1
    assert rows[0][2] == "award.approved"
    assert "action=award.approved" in text


def test_a_summary_containing_commas_and_quotes_stays_one_cell(client, workspace):
    """CSV must not silently split a sentence into three columns."""

    client.put(
        f"/rfqs/{workspace['rfq_id']}",
        headers=workspace["headers"],
        json={"item_name": 'Cable tray, 300mm "heavy"'},
    )

    text = client.get("/audit/export.csv", headers=workspace["headers"]).text

    rows = list(csv.reader(io.StringIO(text)))

    matching = [row for row in rows if len(row) == 11 and row[2] == "rfq.updated"]

    assert len(matching) == 1

    # Columns are [timestamp, action, code, actor, actor type, RFQ number, item,
    # entity, entity id, summary, detail]. The new value is in Detail, and it has to
    # survive as one cell: a comma and a double quote in an item name is ordinary.
    assert '300mm "heavy"' in matching[0][10]

    # An edit reads as a transition, not as a Python dict repr.
    assert "item_name:" in matching[0][10]
    assert "->" in matching[0][10]
