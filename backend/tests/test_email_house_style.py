"""The house style of every email a supplier receives.

Four messages can reach a supplier — the invitation and the three follow-up
templates — and they used to disagree about who was writing. The invitation signed
off as the buyer's company, the reminder signed off as the buyer's *employee*, and
one template signed off as nothing at all. A supplier reading the second one has no
way to tell whether a person or a system wrote it, which is exactly the thing that
makes a request look like spam.

The rule these tests enforce, in one sentence: **the product sends, the buyer is the
counterparty.** Every message introduces Quote Autopilot, names the buyer in the
body, says where a reply actually lands, and signs off as the product with the buyer
named beneath it. Nothing signs as a person.

The wording itself lives in :mod:`agents.email_copy` so the four templates cannot
drift apart again; these tests check both the module and the templates built on it.
"""

import pytest

from agents.email_copy import PRIVACY_NOTE
from agents.email_copy import PRODUCT_NAME
from agents.email_copy import follow_up_context
from agents.email_copy import introduction
from agents.email_copy import reply_note
from agents.email_copy import signature
from agents.followup.prompts import SYSTEM_PROMPT
from agents.followup.prompts import build_deadline_email
from agents.followup.prompts import build_missing_fields_email
from agents.followup.prompts import build_reminder_email

from app.features.invitation.messaging import build_invitation_email

BUYER_COMPANY = "Northwind Industrial"
BUYER_CONTACT = "Sam Okoye"
FORM_LINK = "https://quote-form.example.com/quote/7/tok-123"

#: What every supplier-facing message must end with, byte for byte.
SIGN_OFF = "Best regards,\nQuote Autopilot\non behalf of Northwind Industrial"


# ------------------------------------------------------------------ the module
def test_the_introduction_names_the_buyer_the_item_and_the_product():
    line = introduction("Corridor lighting", "RFQ-2026-001", BUYER_COMPANY)

    assert BUYER_COMPANY in line
    assert "Corridor lighting" in line
    assert "RFQ-2026-001" in line
    assert PRODUCT_NAME in line
    # A supplier must never have to guess which organisation is asking.
    assert line.startswith(BUYER_COMPANY)


def test_the_sign_off_is_the_product_with_the_buyer_named_beneath():
    assert signature(BUYER_COMPANY) == SIGN_OFF


def test_the_reply_note_names_the_contact_and_the_company():
    note = reply_note(BUYER_CONTACT, BUYER_COMPANY)

    assert note == (
        f"Reply to this email to reach {BUYER_CONTACT} at {BUYER_COMPANY} directly."
    )
    # No address offered means no second sentence trailing off into nothing.
    assert note.endswith("directly.")


def test_the_reply_note_offers_an_address_when_there_is_one():
    note = reply_note(BUYER_CONTACT, BUYER_COMPANY, "procurement@northwind.example")

    assert "procurement@northwind.example" in note


def test_the_reply_note_falls_back_to_the_company_without_a_contact():
    assert "reach Northwind Industrial directly" in reply_note(None, BUYER_COMPANY)


def test_the_follow_up_context_names_the_buyer_the_item_and_the_product():
    line = follow_up_context("Bearing 6204", "RFQ-2026-001", BUYER_COMPANY)

    assert line.startswith(PRODUCT_NAME)
    assert BUYER_COMPANY in line
    assert "Bearing 6204" in line
    assert "RFQ-2026-001" in line


# ------------------------------------------------------------------ the emails
def _invitation_body(**overrides) -> str:
    kwargs = {
        "supplier_name": "Acme Facilities",
        "contact_name": "Priya Sharma",
        "rfq_number": "RFQ-2026-001",
        "item_name": "Corridor lighting replacement",
        "specification": "Replace 24 nos. LED fittings and test the circuit.",
        "quantity": 24,
        "unit": "per point",
        "delivery_expectation": "05 Nov 2026",
        "deadline_text": "01 Oct 2026",
        "buyer_company": BUYER_COMPANY,
        "buyer_contact_name": BUYER_CONTACT,
        "buyer_contact_email": "procurement@northwind.example",
        "form_link": FORM_LINK,
        "notes": "Photographs of each completed point are required.",
        "procurement_type": "service",
        "required_field_labels": ["rate", "rate basis", "response time (SLA)"],
        "site_text": "Marina Bay Tower, Block C",
        "required_response_hours": 4,
        "required_accreditations": ["EMA Licensed Electrical Worker (LEW)"],
        "tax_note": "Please quote your rates excluding GST.",
    }
    kwargs.update(overrides)

    return build_invitation_email(**kwargs)[1]


def _reminder_body(**overrides) -> str:
    kwargs = {
        "supplier_name": "Acme Facilities",
        "contact_name": "Priya Sharma",
        "rfq_number": "RFQ-2026-001",
        "item_name": "Corridor lighting replacement",
        "buyer_company": BUYER_COMPANY,
        "buyer_contact_name": BUYER_CONTACT,
        "form_link": FORM_LINK,
        "deadline_text": "01 Oct 2026",
        "sequence": 1,
    }
    kwargs.update(overrides)

    return build_reminder_email(**kwargs)[1]


def _missing_fields_body(**overrides) -> str:
    kwargs = {
        "supplier_name": "Acme Facilities",
        "contact_name": "Priya Sharma",
        "rfq_number": "RFQ-2026-001",
        "item_name": "Corridor lighting replacement",
        "buyer_company": BUYER_COMPANY,
        "buyer_contact_name": BUYER_CONTACT,
        "form_link": FORM_LINK,
        "requested_labels": ["rate basis", "payment terms"],
        "sequence": 1,
    }
    kwargs.update(overrides)

    return build_missing_fields_email(**kwargs)[1]


def _deadline_body(**overrides) -> str:
    kwargs = {
        "supplier_name": "Acme Facilities",
        "contact_name": "Priya Sharma",
        "rfq_number": "RFQ-2026-001",
        "item_name": "Corridor lighting replacement",
        "buyer_company": BUYER_COMPANY,
        "buyer_contact_name": BUYER_CONTACT,
        "form_link": FORM_LINK,
        "deadline_text": "01 Oct 2026",
    }
    kwargs.update(overrides)

    return build_deadline_email(**kwargs)[1]


#: Every message a supplier can receive. Adding a template without adding it here is
#: the failure mode this list exists to catch.
ALL_TEMPLATES = {
    "invitation": _invitation_body,
    "invitation (no contact)": lambda: _invitation_body(
        contact_name=None, buyer_contact_name=None, buyer_contact_email=None
    ),
    "reminder": _reminder_body,
    "reminder (second)": lambda: _reminder_body(sequence=2),
    "reminder (no contact)": lambda: _reminder_body(contact_name=None),
    "reminder (anonymous team)": lambda: _reminder_body(
        contact_name=None, buyer_contact_name=None
    ),
    "missing fields": _missing_fields_body,
    "deadline warning": _deadline_body,
}


@pytest.mark.parametrize("name", sorted(ALL_TEMPLATES))
def test_every_supplier_email_signs_off_as_the_product(name):
    body = ALL_TEMPLATES[name]()

    assert body.rstrip().endswith(SIGN_OFF)


@pytest.mark.parametrize("name", sorted(ALL_TEMPLATES))
def test_every_supplier_email_names_the_buyer_and_the_product_in_the_body(name):
    """The sign-off alone is not enough — it must be said in the message too."""

    body = ALL_TEMPLATES[name]()

    assert PRODUCT_NAME in body
    assert BUYER_COMPANY in body
    # And the product mention is not only the closing line.
    assert PRODUCT_NAME in body.split(SIGN_OFF)[0]


@pytest.mark.parametrize("name", sorted(ALL_TEMPLATES))
def test_no_supplier_email_signs_as_a_person(name):
    body = ALL_TEMPLATES[name]()

    # The buyer's contact is named in the body — the supplier has to know who to
    # reply to — but never as the sender.
    assert f"Best regards,\n{BUYER_CONTACT}" not in body
    assert "Best regards,\nSam" not in body
    # The product, not the buyer, is the name on the last line before "on behalf".
    assert "Best regards,\n" + BUYER_COMPANY not in body


@pytest.mark.parametrize("name", sorted(ALL_TEMPLATES))
def test_every_supplier_email_says_where_a_reply_lands(name):
    body = ALL_TEMPLATES[name]()

    assert "Reply to this email to reach" in body


def test_the_invitation_introduces_the_product_where_the_buyer_is_named():
    body = _invitation_body()

    opening = body.split("Hello Priya,")[1].strip().splitlines()[0]

    assert PRODUCT_NAME in opening
    assert BUYER_COMPANY in opening
    assert "Corridor lighting replacement" in opening
    assert "RFQ-2026-001" in opening


def test_the_invitation_tells_the_supplier_their_pricing_is_private():
    """The first question a contractor has before bidding is who else sees it."""

    assert PRIVACY_NOTE in _invitation_body()


def test_the_invitation_does_not_ask_a_service_supplier_for_goods_fields():
    """The copy is built from the RFQ's own contract, never a fixed sentence."""

    body = _invitation_body().lower()

    assert "rate basis" in body
    assert "production lead time" not in body
    assert "minimum order quantity" not in body


def test_a_goods_invitation_still_uses_the_goods_vocabulary():
    body = _invitation_body(
        procurement_type="goods",
        unit="carton",
        required_field_labels=["unit price", "minimum order quantity"],
        site_text=None,
        required_response_hours=None,
        required_accreditations=None,
    )

    assert "quantity" in body.lower()
    assert "minimum order quantity" in body.lower()
    assert SIGN_OFF in body


def test_the_invitation_email_has_no_snake_case_identifiers():
    """Internal field names must never reach a supplier."""

    assert "_" not in _invitation_body()


def test_the_invitation_is_plain_text_with_the_link_on_its_own_line():
    body = _invitation_body()

    assert "<" not in body
    assert f"\n{FORM_LINK}\n" in body


# ------------------------------------------------------------- the llm prompt
def test_the_llm_prompt_demands_the_same_house_style():
    """The model writes the same three lines the templates do, or not at all."""

    assert PRODUCT_NAME in SYSTEM_PROMPT
    assert "on behalf of" in SYSTEM_PROMPT
    assert "Reply to this email to reach" in SYSTEM_PROMPT
    # The rules must forbid signing as an employee of the buyer.
    assert "never sign as" in SYSTEM_PROMPT.lower()
