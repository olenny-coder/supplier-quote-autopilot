"""Print the live test links for a locally running instance.

Called by ``dev.cmd`` once the API is up. Waits for ``/health``, signs in as the
demo buyer, and prints every supplier's tokenized form link — which is the one
thing you cannot know without asking the database, because the token is generated
at invitation time.

    uv run python -m scripts.show_links              # used by `dev.cmd start`
    uv run python -m scripts.show_links --timeout 8  # used by `dev.cmd links`
"""

import argparse
import sys
import time

import httpx

API = "http://localhost:8000"
BUYER_EMAIL = "buyer@demo-autopilot.example.com"

BAR = "=" * 74


def wait_for_api(timeout: float = 90.0) -> dict | None:
    """Poll /health until the API answers, or give up.

    A generous default because a cold Neon compute takes seconds and the first
    ``uvicorn`` start on Windows is not instant. ``dev.cmd links`` passes a short
    timeout instead, so asking for links on a stopped instance fails quickly rather
    than looking hung.
    """

    deadline = time.monotonic() + timeout
    shown = False

    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{API}/health", timeout=3.0)

            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError:
            pass

        if not shown:
            print("  waiting for the API to start ", end="", flush=True)
            shown = True

        print(".", end="", flush=True)
        time.sleep(1.5)

    if shown:
        print(" timed out")

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="seconds to wait for the API before giving up",
    )
    args = parser.parse_args()

    print()
    print("Waiting for the backend...")

    health = wait_for_api(args.timeout)

    if health is None:
        print()
        print("  The API is not responding on http://localhost:8000")
        print("  Start it with:   dev.cmd")
        return 1

    print(" ready")
    print()

    llm = health.get("llm", {})
    email = health.get("email", {})
    scheduler = health.get("scheduler", {})

    # ---------------------------------------------------------------- buyer
    try:
        login = httpx.post(
            f"{API}/auth/login",
            json={"email": BUYER_EMAIL, "password": "demo-password-123"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        print(f"  Could not reach the API: {exc}")
        return 1

    print(BAR)
    print("  BUYER DASHBOARD")
    print(BAR)

    if login.status_code != 200:
        print("  No demo buyer yet. Seed one with:   dev.cmd seed")
        print()
    else:
        print(f"  {health.get('app')}  ->  http://localhost:5173")
        print()
        print(f"  email     {BUYER_EMAIL}")
        print("  password  demo-password-123")
        print()

    token = login.json().get("access_token") if login.status_code == 200 else None

    # ------------------------------------------------------- supplier links
    if token:
        headers = {"Authorization": f"Bearer {token}"}

        rfqs = httpx.get(f"{API}/rfqs", headers=headers, timeout=15.0).json()

        if not rfqs:
            print("  No RFQs yet. Load the demo workspace with:   dev.cmd seed")
        else:
            rfq = rfqs[0]

            print(BAR)
            print(f"  SUPPLIER FORM LINKS  (no login — open on a phone)")
            print(f"  RFQ {rfq['rfq_number']} — {rfq['item_name']}")
            print(BAR)

            invitations = httpx.get(
                f"{API}/rfqs/{rfq['id']}/invitations", headers=headers, timeout=15.0
            ).json()

            for invitation in invitations:
                print()
                print(f"  {invitation['supplier_name']}  [{invitation['status']}]")
                print(f"    {invitation['form_link']}")
                print(f"    {invitation['status_reason']}")

            print()

    # ---------------------------------------------------------------- misc
    print(BAR)
    print("  OTHER")
    print(BAR)
    print("  API docs      http://localhost:8000/docs")
    print("  Health        http://localhost:8000/health")
    print("  Supplier form http://localhost:5174/  (a bare link shows 'not valid')")
    print()

    print(f"  AI drafting   {'ON  (' + str(llm.get('model')) + ')' if llm.get('configured') else 'OFF — deterministic fallbacks (no LLM_API_KEY)'}")
    print(f"  Email         {email.get('provider')} ({'prints to the API window, sends nothing' if email.get('provider') == 'console' else 'sends for real'})")
    print(f"  Auto-send     {'ON — reminders go out immediately' if scheduler.get('auto_send_followups') else 'OFF — reminders queue for your approval'}")
    print(f"  Scheduler     {'running every ' + str(scheduler.get('interval_minutes')) + ' min' if scheduler.get('running') else 'disabled'}")
    print()
    print("  Stop everything with:   dev.cmd stop")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
