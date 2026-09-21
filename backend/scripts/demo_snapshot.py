"""Read-only demo snapshot generation.

Kept beside the seed rather than inside the app because it is a build-time job: it
reads a seeded workspace through the same services the API uses and writes the JSON
that ``GET /demo/workspace`` serves. Nothing in the request path imports this.

Two protections, because the failure mode is publishing somebody's real data:

1. **The workspace must belong to the fictional demo account.** Dumping is refused
   for any other buyer, so pointing this at a deployment with real tenders in it
   produces an error rather than a file.
2. **Every value is scrubbed anyway.** Addresses become ``example.com``, invitation
   tokens are replaced, and form links are marked as samples. Belt and braces: if
   the first guard is ever wrong, the second still keeps real data out of a public
   file.
"""

from typing import Any

import re

from sqlalchemy import select

from app.core.mixins import utcnow
from app.features.rfq.model import RFQ
from app.features.rfq.service import RFQService

#: Where the snapshot is written by default. Relative to the repository root so a
#: regeneration lands on the file the app actually reads.
DEFAULT_DEMO_DESTINATION = (
    "app/features/demo/workspace.json"
)

#: The literal used in place of a real invitation token. It is deliberately not a
#: plausible token, so nobody mistakes one of these for a working link.
DEMO_TOKEN = "DEMO-TOKEN-NOT-VALID"

#: Host used in every published form link: the reserved documentation domain, so it
#: is unambiguously a sample and can never resolve to a real deployment.
DEMO_FORM_HOST = "https://quote-form.example.com"

#: Any ``/quote/<id>/<token>`` on any host, in any string.
#:
#: The key-driven pass below cannot see a link that is *inside* a value, and the
#: follow-up bodies are exactly that: each one embeds the supplier's full invitation
#: URL, token and all. A sanitiser that only knows about field names would have
#: published four live tokens in prose. This pattern is applied to the serialised
#: JSON as a second pass, so a future field that embeds a link is covered too.
_QUOTE_LINK_RE = re.compile(r"https?://[^\s\"'<>]*?/quote/(\d+)/[A-Za-z0-9_\-]{12,}")

#: Domains that are safe to publish. Anything else is replaced wholesale rather
#: than partially masked, because a half-masked address is still an address.
SAFE_DOMAINS = ("example.com", "example.org", "example.net")


class NotTheDemoWorkspaceError(RuntimeError):
    """Raised when asked to publish a workspace that is not the seeded demo."""


def _safe_email(value: str | None, fallback: str = "supplier@example.com") -> str | None:
    """Publish an address only if it is on a documentation domain."""

    if not value:
        return value

    domain = value.rsplit("@", 1)[-1].lower()

    if any(domain.endswith(safe) for safe in SAFE_DOMAINS):
        return value

    return fallback


def sanitise_for_demo(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip anything from an API-shaped payload that must not be published.

    Recursive and key-driven rather than model-driven: a new field added to a
    response tomorrow is scrubbed the moment it is named like a secret, and any
    field not named here is still only ever published if the *workspace* passed the
    ownership check in :func:`dump_demo`.
    """

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            cleaned: dict[str, Any] = {}

            for key, value in node.items():
                if key in {"token", "token_hint", "scheduler_secret", "secret_key"}:
                    continue

                if key == "form_link" and value:
                    # Keep the shape a buyer recognises, but make it obvious the
                    # link is part of the sample. A live token here would be a
                    # working credential to somebody's invitation.
                    cleaned[key] = _demo_form_link(value)
                    continue

                if key.endswith("_email") or key in {"email", "to_email", "reply_to"}:
                    cleaned[key] = _safe_email(
                        value if isinstance(value, str) else None
                    )
                    continue

                cleaned[key] = walk(value)

            return cleaned

        if isinstance(node, list):
            return [walk(item) for item in node]

        return node

    return walk(payload)


def _demo_form_link(link: str) -> str:
    """A form link on the placeholder host, with the token replaced.

    The host is replaced because the snapshot is generated on whatever machine ran
    the seed — usually a laptop, where ``PUBLIC_FORM_URL`` is
    ``http://localhost:5174``. Serving that on a deployed demo would show every
    visitor a link to their own machine, which reads as a broken product.

    The token is replaced because it is a **credential**: a published invitation
    token is a working key to somebody's invitation, whether or not the suppliers in
    this workspace are fictional.
    """

    match = re.search(r"/quote/(\d+)/", str(link))

    rfq_id = match.group(1) if match else "1"

    return f"{DEMO_FORM_HOST}/quote/{rfq_id}/{DEMO_TOKEN}"


def scrub_links_in_text(serialised: str) -> tuple[str, int]:
    """Replace every ``/quote/<id>/<token>`` URL anywhere in the serialised JSON.

    Returns the text and how many links were rewritten, so the caller can refuse to
    publish if the count is unexpectedly zero (which would mean the workspace has no
    invitations and the demo is not worth serving).
    """

    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1

        return f"{DEMO_FORM_HOST}/quote/{match.group(1)}/{DEMO_TOKEN}"

    return _QUOTE_LINK_RE.sub(replace, serialised), count


def build_demo_payload(db, user, *, buyer_label: str) -> dict[str, Any]:
    """The full snapshot: taxonomy, dashboard summary, and one entry per RFQ.

    Every value comes from the real services — ``RFQService.to_response``,
    ``ComparisonService.quote_summary`` and ``ComparisonService.to_response`` — so
    the demo shows exactly what an authenticated buyer would see, and cannot drift
    into a hand-maintained imitation of it.
    """

    from app.features.comparison.repository import latest_for_rfq
    from app.features.comparison.service import ComparisonService
    from app.features.followup import repository as followup_repository
    from app.features.invitation.service import InvitationService
    from app.features.rfq.router import get_meta_options

    rfqs = list(
        db.scalars(
            select(RFQ).where(RFQ.user_id == user.id).order_by(RFQ.id.asc())
        ).all()
    )

    workspaces: list[dict[str, Any]] = []

    for rfq in rfqs:
        # Queried rather than read from `rfq.quotes`: a relationship collection is
        # cached on the instance and can be stale inside a long-lived session, which
        # is exactly how a quote goes missing from a snapshot.
        quotes = ComparisonService.load_quotes(db, rfq.id)

        comparison = latest_for_rfq(db, rfq.id)

        workspaces.append(
            {
                "rfq": RFQService.to_response(
                    rfq, RFQService.counts(db, [rfq.id]).get(rfq.id)
                ).model_dump(mode="json"),
                "invitations": [
                    InvitationService.to_response(
                        invitation, rfq, invitation.quote
                    ).model_dump(mode="json")
                    for invitation in InvitationService.list_for_rfq(
                        db=db, rfq_id=rfq.id
                    )
                ],
                "quotes": [
                    ComparisonService.quote_summary(quote).model_dump(mode="json")
                    for quote in quotes
                ],
                "followups": [
                    followup_repository.to_response(followup).model_dump(mode="json")
                    for followup in followup_repository.list_for_rfq(
                        db=db, rfq_id=rfq.id, limit=100
                    )
                ],
                "comparison": (
                    ComparisonService.to_response(comparison).model_dump(mode="json")
                    if comparison is not None
                    else None
                ),
            }
        )

    return {
        "generated_at": utcnow().isoformat(),
        "buyer_label": buyer_label,
        "meta": get_meta_options().model_dump(mode="json"),
        "workspaces": workspaces,
    }


def dump_demo(db, user, *, destination: str, demo_email: str) -> str:
    """Write the sanitised snapshot and return a one-line description.

    ``demo_email`` is the fictional account the workspace must belong to. Anything
    else is refused: the point of this guard is that a well-meaning operator cannot
    publish their own tenders by running one command against the wrong database.
    """

    import json
    from pathlib import Path

    if (user.email or "").lower() != demo_email.lower():
        raise NotTheDemoWorkspaceError(
            f"Refusing to publish a demo snapshot for {user.email!r}. The demo "
            f"workspace must belong to the seeded demo account ({demo_email}). "
            f"Run with --reset to rebuild it, or point DATABASE_URL at a scratch "
            f"database — never at a real workspace."
        )

    payload = sanitise_for_demo(
        build_demo_payload(db, user, buyer_label=buyer_label_for(user))
    )

    rfq_count = len(payload["workspaces"])
    quote_count = sum(len(w["quotes"]) for w in payload["workspaces"])
    comparison_count = sum(1 for w in payload["workspaces"] if w["comparison"])

    if rfq_count == 0 or quote_count == 0:
        raise NotTheDemoWorkspaceError(
            "The workspace is empty, so there is nothing to demo. Run the seed "
            "without --skip-compare first."
        )

    if comparison_count == 0:
        raise NotTheDemoWorkspaceError(
            "No comparison was stored, so the demo would show no scored result. "
            "Run the seed without --skip-compare."
        )

    # Resolved against the repository root so the default lands beside the module
    # that serves it, whatever directory the script was run from.
    path = Path(destination)

    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path

    path.parent.mkdir(parents=True, exist_ok=True)

    serialised, scrubbed = scrub_links_in_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)
    )

    # The final gate. If a real token-shaped string is still in the text, something
    # in the payload embeds a credential in a way this module does not understand,
    # and the correct response is to publish nothing rather than a file that leaks.
    #
    # `DEMO_TOKEN` is itself token-shaped, so it has to be excluded here — otherwise
    # the gate reports its own replacements as survivors and refuses to publish a
    # perfectly clean snapshot.
    leftovers = [
        match.group(0)
        for match in _QUOTE_LINK_RE.finditer(serialised)
        if DEMO_TOKEN not in match.group(0)
    ]

    if leftovers:
        raise NotTheDemoWorkspaceError(
            f"{len(leftovers)} invitation link(s) survived sanitisation and would "
            f"have been published. Refusing to write the snapshot. This is a bug in "
            f"demo_snapshot.py, not in the workspace. First survivor: "
            f"{leftovers[0][:120]}"
        )

    with path.open("w", encoding="utf-8") as handle:
        handle.write(serialised)

    size_kb = path.stat().st_size / 1024

    return (
        f"{rfq_count} RFQ(s), {quote_count} quote(s), {comparison_count} scored "
        f"comparison(s), {scrubbed} form link(s) replaced -> {path} ({size_kb:.0f} kB)"
    )


def buyer_label_for(user) -> str:
    """What the demo calls the buyer. Never the real company name of a user."""

    return "Marina Facilities Management Pte Ltd"
