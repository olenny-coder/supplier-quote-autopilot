"""Services, end to end through the public HTTP API.

The rest of the suite pins ``procurement_type="goods"``, so before this module the
nine criteria, the accreditation cap, GST derivation, the service rate bases,
``/meta/options`` and the whole service submission contract were exercised only by
the seed script and by hand.

Going through HTTP rather than the services is deliberate: it is the only way to
catch the class of defect where a service works but a router, a schema or a
dependency does not. One such defect is guarded here explicitly — ``PublicQuoteSubmit``
silently drops unknown keys, so a supplier form posting ``response_time_hours``
against a schema that declared ``response_time`` received a cheerful **201** while
the SLA, the materials markup and every accreditation were discarded. Because a
services RFQ *requires* an SLA, that turned every services quote into an
"incomplete" one, and the follow-up engine then chased a contractor for a number
they had already typed in. Both spellings are accepted now, and both are tested.
"""

from datetime import date
from datetime import timedelta

import pytest

from app.core.mixins import utcnow

LEW = "EMA Licensed Electrical Worker (LEW)"
BIZSAFE = "bizSAFE Level 3"

BUYER = {
    "email": "facilities@marina-fm.example.com",
    "password": "correct-horse-battery",
    "full_name": "Dana Whitfield",
    "company_name": "Marina Facilities Management Pte Ltd",
    "contact_email": "procurement@marina-fm.example.com",
    "contact_phone": "+65 6221 0142",
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

#: A completed submission using the names the supplier form actually posts.
COMPLETE_QUOTE = {
    "supplier_name": "Teck Guan Facilities Services Pte Ltd",
    "currency": "SGD",
    "unit_price": "162.00",
    "unit": "per point",
    "response_time_hours": "2",
    "callout_charge": "120",
    "labour_rate": "74",
    "materials_markup_pct": "12",
    "compliance_accreditations": [LEW, BIZSAFE],
    "gst_rate": "9",
    "payment_terms": "Net 30",
    "validity_date": (date.today() + timedelta(days=300)).isoformat(),
    "company_website": "",
}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def buyer(client):
    """A registered buyer with a live Singapore services RFQ and two invitations."""

    registration = client.post("/auth/register", json=BUYER)

    assert registration.status_code == 201, registration.text

    headers = _auth(registration.json()["access_token"])

    rfq = client.post(
        "/rfqs",
        headers=headers,
        json={
            "item_name": "Corridor lighting replacement and AHU pipe leak — Block C",
            "specification": "24 nos. LED fittings and the AHU riser isolation valve.",
            "category": "Electrical Minor Works",
            "quantity": 24,
            "unit": "per point",
            "currency": "SGD",
            "gst_rate": 9,
            "delivery_expectation": (date.today() + timedelta(days=45)).isoformat(),
            "deadline": (utcnow() + timedelta(days=10)).isoformat(),
            "site_name": "Marina Bay Tower, Block C",
            "site_address": "12 Marina Boulevard, Singapore 018982",
            "site_access_notes": "Access 9am-5pm. Lift booking 48h ahead.",
            "required_response_hours": 4,
            "required_accreditations": [LEW, BIZSAFE],
            "notes": "Photographs of each completed point required.",
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


# ============================================================== the taxonomy API
def test_meta_options_needs_no_credentials_and_leaks_nothing_buyer_specific(client):
    """The supplier form needs the same vocabulary, and has no account."""

    response = client.get("/meta/options")

    assert response.status_code == 200

    body = response.json()

    assert body["base_currency"] == "SGD"
    assert body["default_procurement_type"] == "service"
    assert body["default_gst_rate"] == 9.0

    # Supplier-facing labels, but no buyer, supplier or RFQ data of any kind.
    assert "email" not in str(body.get("required_field_labels", {})).lower()


def test_meta_options_publishes_the_whole_service_taxonomy(client):
    body = client.get("/meta/options").json()

    assert body["procurement_types"] == ["service", "goods"]

    assert len(body["service_categories"]) == 19
    assert "Electrical Minor Works" in body["service_categories"]
    assert "Plumbing & Sanitary Minor Works" in body["service_categories"]
    assert "Painting & Decorating" in body["service_categories"]

    assert len(body["service_rate_bases"]) == 10
    assert "per point" in body["service_rate_bases"]
    assert "lump sum" in body["service_rate_bases"]

    assert len(body["common_accreditations"]) == 13
    assert LEW in body["common_accreditations"]
    assert BIZSAFE in body["common_accreditations"]

    # Nine criteria, each with a description the weight editor renders verbatim.
    assert [c["key"] for c in body["criteria"]] == [
        "price",
        "response_time",
        "lead_time",
        "compliance",
        "payment_terms",
        "moq",
        "validity",
        "warranty",
        "risk",
    ]
    for criterion in body["criteria"]:
        assert criterion["label"].strip()
        assert criterion["description"].strip(), criterion["key"]


def test_meta_options_serves_labels_per_procurement_type(client):
    """A flat map showed a goods RFQ the service vocabulary, and vice versa."""

    labels = client.get("/meta/options").json()["required_field_labels"]

    assert set(labels) == {"service", "goods"}

    assert labels["service"]["moq"] == "minimum callout charge"
    assert labels["goods"]["moq"] == "minimum order quantity"

    assert labels["service"]["unit"] == "rate basis"
    assert labels["goods"]["unit"] == "unit of measure"

    assert labels["service"]["lead_time"] == "mobilisation time"
    assert labels["goods"]["lead_time"] == "lead time"


def test_meta_options_reports_the_per_type_contracts_and_weights(client):
    body = client.get("/meta/options").json()

    assert body["required_fields"]["service"] == [
        "unit_price",
        "currency",
        "unit",
        "response_time",
        "payment_terms",
        "validity_date",
    ]
    assert "incoterms" in body["required_fields"]["goods"]
    assert "response_time" not in body["required_fields"]["goods"]

    assert body["default_weights"]["service"]["response_time"] == 0.15
    assert body["default_weights"]["service"]["moq"] == 0.0
    assert body["default_weights"]["goods"]["response_time"] == 0.0
    assert body["default_weights"]["goods"]["moq"] == 0.05


# ================================================================== creating RFQs
def test_a_new_rfq_is_a_services_rfq_in_sgd_with_gst(client):
    """The product default, end to end: no field has to be named to get it."""

    registration = client.post("/auth/register", json={**BUYER, "email": "d@x.example.com"})
    headers = _auth(registration.json()["access_token"])

    response = client.post(
        "/rfqs",
        headers=headers,
        json={
            "item_name": "Quarterly ACMV servicing",
            "specification": "12 split-unit AHUs, quarterly.",
            "delivery_expectation": (date.today() + timedelta(days=30)).isoformat(),
        },
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["procurement_type"] == "service"
    assert body["currency"] == "SGD"
    assert float(body["gst_rate"]) == 9.0

    # The rate basis defaults to the first one that makes sense for services, not to
    # a goods unit of measure.
    assert body["unit"] == "per job"

    # The services contract applies without anyone asking for it — and notably does
    # not include MOQ or Incoterms.
    assert body["required_fields"] == [
        "unit_price",
        "currency",
        "unit",
        "response_time",
        "payment_terms",
        "validity_date",
    ]

    # Labels are the services wording, from the same table the follow-up emails use.
    assert body["required_field_labels"] == [
        "rate",
        "currency",
        "rate basis",
        "response time (SLA)",
        "payment terms",
        "rates valid until",
    ]


def test_a_goods_rfq_still_defaults_to_pieces_and_its_own_contract(client):
    """A single hard-coded unit default would silently break one of the two paths."""

    registration = client.post("/auth/register", json={**BUYER, "email": "g@x.example.com"})
    headers = _auth(registration.json()["access_token"])

    response = client.post(
        "/rfqs",
        headers=headers,
        json={
            "item_name": "Hex bolt M10",
            "specification": "SS304",
            "procurement_type": "goods",
            "delivery_expectation": (date.today() + timedelta(days=30)).isoformat(),
        },
    )

    body = response.json()

    assert body["procurement_type"] == "goods"
    assert body["unit"] == "pcs"
    assert "incoterms" in body["required_fields"]
    assert "response_time" not in body["required_fields"]
    assert "minimum order quantity" in body["required_field_labels"]


def test_an_rfq_of_only_24_points_priced_per_job_would_exclude_every_quote(buyer):
    """The RFQ's own basis is what suppliers are asked to price against."""

    assert buyer["rfq"]["unit"] == "per point"
    assert buyer["rfq"]["quantity"] == 24
    assert buyer["rfq"]["category"] == "Electrical Minor Works"


# ============================================================== the supplier view
def test_the_preview_gives_the_supplier_everything_the_service_form_needs(client, buyer):
    body = client.get(public_path(buyer)).json()

    assert body["procurement_type"] == "service"
    assert body["category"] == "Electrical Minor Works"
    assert body["unit"] == "per point"
    assert body["quantity"] == 24
    assert body["currency"] == "SGD"

    assert body["site_name"] == "Marina Bay Tower, Block C"
    assert "Marina Boulevard" in body["site_address"]
    assert "Lift booking" in body["site_access_notes"]

    assert body["required_response_hours"] == 4
    assert body["required_accreditations"] == [LEW, BIZSAFE]

    assert body["gst_rate"] == 9.0
    assert "GST" in body["tax_note"]
    assert "excluding" in body["tax_note"]

    # The picker vocabulary and the server-owned labels.
    assert "per point" in body["rate_bases"]
    assert body["required_field_labels"] == [
        "rate",
        "currency",
        "rate basis",
        "response time (SLA)",
        "payment terms",
        "rates valid until",
    ]

    # No buyer secrets, no other supplier, no token echoed back.
    assert "password" not in str(body).lower()
    assert "hashed" not in str(body).lower()


# =========================================================== submitting a quote
def test_a_complete_service_submission_is_recorded_as_complete(client, buyer):
    """The SLA, markup and licences all survive the round trip."""

    response = client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE)

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["completeness"] == "complete", body["missing_field_labels"]
    assert body["missing_field_labels"] == []
    assert body["response_time_hours"] == 2
    assert LEW in body["accreditations"]

    quote = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()[0]

    assert quote["response_time_hours"] == 2
    assert float(quote["callout_charge"]) == 120.0
    assert float(quote["labour_rate"]) == 74.0
    assert float(quote["materials_markup_pct"]) == 12.0
    assert quote["compliance_accreditations"] == [LEW, BIZSAFE]
    assert float(quote["gst_rate"]) == 9.0

    # "per point" survives as the supplier wrote it, rather than collapsing to the
    # internal canonical "point".
    assert quote["unit"] == "per point"


def test_the_alias_spellings_are_accepted_rather_than_silently_discarded(client, buyer):
    """The defect this guards: a 201 with the SLA thrown away.

    ``PublicQuoteSubmit`` had no ``model_config``, so pydantic's default
    ``extra="ignore"`` applied. A form posting the three field names whose spelling
    is not obvious got a success response, and because a services RFQ requires
    ``response_time``, the quote was stored incomplete and then chased.
    """

    response = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Sin Heng M&E Pte Ltd",
            "currency": "SGD",
            "unit_price": "148.00",
            "unit": "per point",
            "response_time": "same day",
            "materials_markup": "15%",
            "accreditations": f"{BIZSAFE}; ISO 9001",
            "payment_terms": "Net 30",
            "validity_date": (date.today() + timedelta(days=200)).isoformat(),
            "company_website": "",
        },
    )

    assert response.status_code == 201, response.text

    quote = client.get(
        f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]
    ).json()[0]

    assert quote["response_time_hours"] == 8          # "same day"
    assert float(quote["materials_markup_pct"]) == 15.0
    assert quote["compliance_accreditations"] == [BIZSAFE, "ISO 9001"]

    # And therefore the quote is not falsely incomplete.
    assert quote["completeness"] == "complete", quote["missing_field_labels"]


def test_an_incomplete_service_submission_is_chased_for_exactly_what_is_missing(
    client, buyer
):
    """Only the genuinely missing fields, in the supplier's own vocabulary."""

    partial = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Sin Heng M&E Pte Ltd",
            "currency": "SGD",
            "unit_price": "148.00",
            "unit": "per point",
            "response_time_hours": "8",
            "company_website": "",
        },
    )

    assert partial.status_code == 201

    body = partial.json()

    assert body["completeness"] == "incomplete"

    # Payment terms and rate validity — and NOT the SLA, which was answered.
    assert body["missing_field_labels"] == ["payment terms", "rates valid until"]

    # The SLA is never asked for again, which is the whole point.
    assert not any("SLA" in label for label in body["missing_field_labels"])

    # The follow-up asks for the same two fields, with the same wording.
    from app.features.followup.service import run_scheduler

    from app.core.database import SessionLocal

    db = SessionLocal()

    try:
        run_scheduler(db)
    finally:
        db.close()

    drafts = client.get(
        f"/rfqs/{buyer['rfq_id']}/follow-ups", headers=buyer["headers"]
    ).json()

    chase = next(item for item in drafts if item["kind"] == "incomplete_quote")

    assert chase["requested_fields"] == ["payment_terms", "validity_date"]
    assert chase["requested_labels"] == ["payment terms", "rates valid until"]
    assert chase["status"] == "draft"

    # Nothing was sent: reminders queue for a human unless auto-send is enabled.
    assert "response time" not in chase["body"].lower()


def test_a_submission_is_satisfied_by_the_services_contract_not_a_goods_one(
    client, buyer
):
    """A goods-shaped submission must NOT count as complete for a services RFQ."""

    response = client.post(
        f"{public_path(buyer)}/quote",
        json={
            "supplier_name": "Wrong shape",
            "currency": "SGD",
            "unit_price": "148.00",
            "unit": "pcs",
            "lead_time": "2 weeks",
            "moq": "100",
            "incoterms": "FOB",
            "company_website": "",
        },
    )

    body = response.json()

    assert body["completeness"] == "incomplete"

    # The SLA is required; MOQ and Incoterms are not even looked for.
    assert "response time (SLA)" in body["missing_field_labels"]
    assert not any("MOQ" in label for label in body["missing_field_labels"])
    assert not any("Incoterms" in label for label in body["missing_field_labels"])


# ======================================================= comparison and award
def _submit_two(client, buyer):
    """One complete compliant quote and one cheaper unlicensed one."""

    first = client.post(f"{public_path(buyer)}/quote", json=COMPLETE_QUOTE)

    assert first.status_code == 201, first.text

    second = client.post(
        f"{public_path(buyer, buyer['secondary'])}/quote",
        json={
            "supplier_name": "Sin Heng M&E Pte Ltd",
            "currency": "SGD",
            "unit_price": "148.00",
            "unit": "per point",
            "response_time_hours": "8",
            "callout_charge": "180",
            "materials_markup_pct": "15",
            # Deliberately missing the LEW the buyer requires.
            "compliance_accreditations": [BIZSAFE],
            "gst_rate": "9",
            "payment_terms": "Net 30",
            "validity_date": (date.today() + timedelta(days=200)).isoformat(),
            "company_website": "",
        },
    )

    assert second.status_code == 201, second.text


def test_the_quote_summary_reports_the_missing_licence_from_the_engine(client, buyer):
    """The dashboard must not have to re-derive which licences are absent."""

    _submit_two(client, buyer)

    quotes = client.get(f"/rfqs/{buyer['rfq_id']}/quotes", headers=buyer["headers"]).json()

    by_supplier = {quote["supplier_name"]: quote for quote in quotes}

    assert by_supplier["Sin Heng M&E Pte Ltd"]["missing_accreditations"] == [LEW]
    assert by_supplier["Teck Guan Facilities Services Pte Ltd"][
        "missing_accreditations"
    ] == []

    assert by_supplier["Sin Heng M&E Pte Ltd"]["response_time_hours"] == 8
    assert by_supplier["Sin Heng M&E Pte Ltd"]["unit"] == "per point"


def test_the_comparison_ranks_the_compliant_quote_first_and_says_why(client, buyer):
    _submit_two(client, buyer)

    response = client.get(
        f"/rfqs/{buyer['rfq_id']}/comparison", headers=buyer["headers"]
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["base_currency"] == "SGD"
    assert body["weights"]["response_time"] == 0.15
    assert body["weights"]["moq"] == 0.0
    assert body["is_conclusive"] is True

    results = {item["supplier_name"]: item for item in body["results"]}

    compliant = results["Teck Guan Facilities Services Pte Ltd"]
    unlicensed = results["Sin Heng M&E Pte Ltd"]

    assert compliant["rank"] == 1
    assert unlicensed["rank"] == 2

    assert unlicensed["comparable"] is True
    assert unlicensed["composite_score"] <= 25.0
    assert unlicensed["missing_accreditations"] == [LEW]

    # The cheaper quote is genuinely cheaper, so the ranking is not a price artefact.
    assert unlicensed["total_base"] < compliant["total_base"]

    assert body["recommended_quote_id"] == compliant["quote_id"]

    assert any(
        "Does not hold required accreditation" in flag for flag in unlicensed["risk_flags"]
    )

    assert LEW in body["rationale"]


def test_the_comparison_costs_the_callout_and_discloses_derived_gst(client, buyer):
    _submit_two(client, buyer)

    body = client.get(
        f"/rfqs/{buyer['rfq_id']}/comparison", headers=buyer["headers"]
    ).json()

    compliant = next(
        item
        for item in body["results"]
        if item["supplier_name"] == "Teck Guan Facilities Services Pte Ltd"
    )

    breakdown = compliant["breakdown"]

    # 162.00 x 24 points + 120.00 callout, then 9% GST.
    assert float(breakdown["goods"]) == 3888.0
    assert float(breakdown["callout"]) == 120.0
    assert float(breakdown["taxes"]) == 360.72
    assert float(breakdown["total"]) == 4368.72
    assert breakdown["tax_derived_from_rate"] is True

    assert float(compliant["total_base"]) == 4368.72

    # The basis is shown as the supplier wrote it.
    assert compliant["unit_original"] == "per point"

    assert any(
        "GST added at 9% from the rate stated on the quote" in flag
        for flag in compliant["risk_flags"]
    )


def test_a_manually_entered_service_quote_is_assessed_against_the_service_contract(
    client, buyer
):
    """The manual/imported path builds its own field map, and it had to grow too."""

    response = client.post(
        f"/rfqs/{buyer['rfq_id']}/quotes",
        headers=buyer["headers"],
        json={
            "supplier_name": "Phone quote",
            "currency": "SGD",
            "unit_price": "155.00",
            "unit": "per point",
            "lead_time": 3,
            "response_time_hours": 4,
            "callout_charge": "150.00",
            "compliance_accreditations": [LEW, BIZSAFE],
            "payment_terms": "Net 30",
            "validity_date": (date.today() + timedelta(days=180)).isoformat(),
        },
    )

    assert response.status_code == 201, response.text

    body = response.json()

    # Every service field the buyer typed was seen by the completeness check.
    assert body["completeness"] == "complete", body["missing_field_labels"]
    assert body["missing_field_labels"] == []
    assert body["response_time_hours"] == 4
    assert body["missing_accreditations"] == []


def test_the_comparison_serves_the_requirements_it_was_scored_against(client, buyer):
    """The accreditation column needs the RFQ's required list, not just the shortfall.

    The engine has always computed both, but ``ComparisonResponse`` did not declare
    them, so ``to_response`` dropped them. The comparison table's accreditation
    column therefore read "None required" on a services RFQ that required a licensed
    electrician, and the "N of M required" line and its missing-licence chips could
    never render — the shortfall survived only as a risk flag, which is the wrong
    place for a licence the work cannot lawfully proceed without.
    """

    _submit_two(client, buyer)

    body = client.get(
        f"/rfqs/{buyer['rfq_id']}/comparison", headers=buyer["headers"]
    ).json()

    assert body["procurement_type"] == "service"
    assert body["required_accreditations"] == [LEW, BIZSAFE]

    unlicensed = next(
        item
        for item in body["results"]
        if item["supplier_name"] == "Sin Heng M&E Pte Ltd"
    )

    assert unlicensed["missing_accreditations"] == [LEW]

    held = [
        item
        for item in unlicensed["compliance_accreditations"]
        if item in body["required_accreditations"]
    ]

    assert len(held) == 1, "one of the two required licences is held"


def test_a_goods_rfq_reports_no_required_accreditations(client):
    """Absence of a requirement must read as absence, not as a silent pass."""

    registration = client.post(
        "/auth/register", json={**BUYER, "email": "goods-comp@x.example.com"}
    )
    headers = _auth(registration.json()["access_token"])

    rfq = client.post(
        "/rfqs",
        headers=headers,
        json={
            "item_name": "Hex bolt",
            "specification": "SS304",
            "procurement_type": "goods",
            "quantity": 100,
            "unit": "pcs",
            "delivery_expectation": (date.today() + timedelta(days=30)).isoformat(),
        },
    ).json()

    created = client.post(
        f"/rfqs/{rfq['id']}/quotes",
        headers=headers,
        json={
            "supplier_name": "Fastener Co",
            "currency": "SGD",
            "unit_price": "2.50",
            "unit": "pcs",
            "lead_time": 14,
            "moq": 100,
            "payment_terms": "Net 30",
            "incoterms": "FOB",
            "validity_date": (date.today() + timedelta(days=60)).isoformat(),
        },
    )

    assert created.status_code == 201, created.text

    body = client.get(f"/rfqs/{rfq['id']}/comparison", headers=headers).json()

    assert body["procurement_type"] == "goods"
    assert body["required_accreditations"] == []


def test_awarding_still_requires_an_explicit_human_decision(client, buyer):
    """The guardrail is unchanged by the pivot, and an incomplete quote needs a
    deliberate override even to be considered."""

    _submit_two(client, buyer)

    comparison = client.get(
        f"/rfqs/{buyer['rfq_id']}/comparison", headers=buyer["headers"]
    ).json()

    recommended = comparison["recommended_quote_id"]

    missing_note = client.post(
        f"/rfqs/{buyer['rfq_id']}/comparison/approve",
        headers=buyer["headers"],
        json={"quote_id": recommended, "decision": "approved"},
    )

    # The note is mandatory on an award.
    assert missing_note.status_code == 422

    approved = client.post(
        f"/rfqs/{buyer['rfq_id']}/comparison/approve",
        headers=buyer["headers"],
        json={
            "quote_id": recommended,
            "decision": "approved",
            "note": "Lowest compliant bid; LEW verified on the licence card.",
        },
    )

    assert approved.status_code in (200, 201), approved.text

    awarded = client.get(f"/rfqs/{buyer['rfq_id']}", headers=buyer["headers"]).json()

    assert awarded["status"] == "awarded"
