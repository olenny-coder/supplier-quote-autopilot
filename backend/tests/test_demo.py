"""Demo mode — a read-only view of the product with no account.

The product claim under test is a security claim, not a UI one: an anonymous visitor
can see what the engine computes, and cannot run a live request through. That has to
hold in the route table rather than in whatever the front end chooses to render, so
the tests below attack the API directly.

Three properties:

1. **Nothing under ``/demo`` can write.** Every other verb is a 405, and the set of
   demo routes is asserted to be exactly one GET — so adding a mutating demo route
   fails here before it can ship.
2. **Nothing published is a credential.** No invitation token, no real form link, no
   address outside a documentation domain. The follow-up bodies embed the supplier's
   invitation URL in prose, which is exactly the case a field-name-driven scrubber
   misses, so the check is over the raw response text.
3. **It is the engine's own output.** The demo is only worth anything if it shows the
   real scoring: the service weights, the cap on a quote missing a required licence,
   the missing-accreditation list. Those are asserted against the payload.
"""

import json
import re

import pytest

from app.features.demo import workspace as demo_workspace
from app.main import app

DEMO_PATH = "/demo/workspace"


@pytest.fixture
def demo_client(client):
    """The demo snapshot must be readable with no credentials at all."""

    demo_workspace.load_workspace.cache_clear()

    yield client

    demo_workspace.load_workspace.cache_clear()


# ============================================================== reading the demo
def test_the_demo_needs_no_credentials(demo_client):
    response = demo_client.get(DEMO_PATH)

    assert response.status_code == 200, response.text


def test_the_demo_is_not_behind_the_auth_layer(demo_client):
    """A stale or malformed bearer token must not lock a visitor out of the demo."""

    response = demo_client.get(
        DEMO_PATH, headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == 200


def test_the_demo_says_what_it_is(demo_client):
    """The disclaimer is served, not written into the front end, so the two cannot
    disagree about what the demo does."""

    body = demo_client.get(DEMO_PATH).json()

    assert "sample workspace" in body["disclaimer"].lower()
    assert "nothing here is saved" in body["disclaimer"].lower()
    assert body["buyer_label"]


def test_the_demo_carries_what_a_buyer_comes_to_see(demo_client):
    body = demo_client.get(DEMO_PATH).json()

    assert body["meta"]["base_currency"] == "SGD"
    assert body["meta"]["default_procurement_type"] == "service"
    assert len(body["meta"]["criteria"]) == 9

    assert len(body["workspaces"]) >= 1

    workspace = body["workspaces"][0]

    for key in ("rfq", "invitations", "quotes", "followups", "comparison"):
        assert key in workspace, key

    assert workspace["quotes"], "a demo with no quotes shows nothing"
    assert workspace["comparison"] is not None


# ======================================================== it cannot be written to
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_no_write_verb_reaches_a_demo_route(demo_client, method):
    """The failure a visitor would experience is a 405, not a 200 that quietly wrote."""

    response = getattr(demo_client, method)(DEMO_PATH)

    assert response.status_code == 405


def test_the_demo_route_table_is_exactly_one_get():
    """A mutating demo route would fail here before it could ship.

    This is the assertion that keeps "view only" true: it is not enough for the
    front end to hide its buttons, because the front end is not what an attacker
    talks to.

    Asserted against the published OpenAPI document rather than ``app.routes``,
    because ``include_router`` no longer flattens a router's routes into the app's
    list — it keeps an ``_IncludedRouter`` — so the schema is both the honest
    surface and the one a visitor can read at ``/docs``.
    """

    spec = app.openapi()

    demo_paths = {
        path: sorted(ops) for path, ops in spec["paths"].items() if path.startswith("/demo")
    }

    assert demo_paths == {DEMO_PATH: ["get"]}, demo_paths


# ==================================================== nothing published is secret
def test_no_field_named_like_a_credential_is_published(demo_client):
    raw = demo_client.get(DEMO_PATH).text

    for forbidden in ('"token"', '"token_hint"', '"secret_key"', '"scheduler_secret"'):
        assert forbidden not in raw, forbidden


def test_a_form_link_is_marked_as_a_sample(demo_client):
    raw = demo_client.get(DEMO_PATH).text

    assert "DEMO-TOKEN-NOT-VALID" in raw

    # The host is a reserved documentation domain, never a deployment's own.
    links = re.findall(r'"form_link":\s*"([^"]+)"', raw)

    assert links

    for link in links:
        assert link.startswith("https://quote-form.example.com/quote/")


def test_no_working_invitation_token_survives_anywhere(demo_client):
    """Including inside the follow-up email bodies, which embed the link in prose.

    That is the case a key-driven scrubber cannot see, and the reason the sanitiser
    also rewrites the serialised text.
    """

    raw = demo_client.get(DEMO_PATH).text

    shaped = [
        match
        for match in re.findall(r"/quote/\d+/[A-Za-z0-9_\-]{12,}", raw)
        if "DEMO-TOKEN" not in match
    ]

    assert shaped == [], f"{len(shaped)} token-shaped string(s) published"


def test_no_localhost_leaks_into_a_deployed_demo(demo_client):
    """The snapshot is generated on a laptop, where PUBLIC_FORM_URL is localhost."""

    assert "localhost" not in demo_client.get(DEMO_PATH).text


def test_every_published_address_is_on_a_documentation_domain(demo_client):
    raw = demo_client.get(DEMO_PATH).text

    addresses = re.findall(r"[\w.\-+]+@[\w.\-]+", raw)

    assert addresses, "the demo should show supplier contact details"

    for address in addresses:
        domain = address.rstrip(".").rsplit("@", 1)[-1].lower()

        assert domain.endswith(("example.com", "example.org", "example.net")), address


# ============================================ it is the engine's real output
def test_the_demo_shows_the_service_weights_the_engine_used(demo_client):
    comparison = demo_client.get(DEMO_PATH).json()["workspaces"][0]["comparison"]

    assert comparison["base_currency"] == "SGD"
    assert comparison["weights"]["response_time"] == 0.15
    assert comparison["weights"]["moq"] == 0.0
    assert comparison["is_conclusive"] is True


def test_the_demo_shows_a_quote_capped_for_a_missing_licence(demo_client):
    """The single most valuable thing to demonstrate: cheap and unlicensed loses.

    If the snapshot were ever regenerated without the cap firing, the demo would be
    showing the product's most important guardrail as absent.
    """

    comparison = demo_client.get(DEMO_PATH).json()["workspaces"][0]["comparison"]

    capped = [item for item in comparison["results"] if item["missing_accreditations"]]

    assert capped, "no quote in the demo is missing a required accreditation"

    for item in capped:
        assert item["composite_score"] <= 25.0, item["supplier_name"]
        assert item["rank"] is not None, "a capped quote must stay visible and ranked"

    winner = next(
        item
        for item in comparison["results"]
        if item["quote_id"] == comparison["recommended_quote_id"]
    )

    assert winner["missing_accreditations"] == []


def test_the_demo_shows_derived_gst_in_the_cost_breakdown(demo_client):
    comparison = demo_client.get(DEMO_PATH).json()["workspaces"][0]["comparison"]

    derived = [
        item
        for item in comparison["results"]
        if item["breakdown"].get("tax_derived_from_rate")
    ]

    assert derived, "no quote in the demo demonstrates tax derived from a stated rate"

    for item in derived:
        assert float(item["breakdown"]["taxes"]) > 0


def test_the_demo_shows_follow_up_drafts_with_the_missing_fields_named(demo_client):
    workspace = demo_client.get(DEMO_PATH).json()["workspaces"][0]

    drafts = [
        followup
        for followup in workspace["followups"]
        if followup["kind"] == "incomplete_quote"
    ]

    assert drafts, "the demo should show a targeted chase"

    chase = drafts[0]

    assert chase["requested_fields"], "the chase must name the fields it wants"
    assert chase["requested_labels"], "and in the supplier's own vocabulary"


# ============================================================ turning it off
def test_demo_mode_can_be_switched_off(monkeypatch):
    """A deployment that should not carry a demo says so with one variable."""

    from app.core.config import settings

    demo_workspace.load_workspace.cache_clear()
    monkeypatch.setattr(settings, "DEMO_MODE_ENABLED", False)

    try:
        with pytest.raises(Exception) as excinfo:
            demo_workspace.get_workspace()

        assert "no demo workspace" in str(excinfo.value).lower()
    finally:
        demo_workspace.load_workspace.cache_clear()


def test_a_missing_snapshot_is_a_404_not_a_crash(monkeypatch, demo_client):
    demo_workspace.load_workspace.cache_clear()
    monkeypatch.setattr(demo_workspace, "WORKSPACE_FILE", demo_workspace.Path("nope.json"))

    try:
        response = demo_client.get(DEMO_PATH)

        assert response.status_code == 404
    finally:
        demo_workspace.load_workspace.cache_clear()


# ============================================================ the snapshot itself
def test_the_committed_snapshot_parses_and_is_not_empty():
    """The file is a build artefact in version control, so it can be checked."""

    path = demo_workspace.WORKSPACE_FILE

    assert path.exists(), "run: python -m scripts.seed_demo --dump-demo"

    document = json.loads(path.read_text(encoding="utf-8"))

    assert document["workspaces"]
    assert document["meta"]["criteria"]
