"""Print the live test links for a locally running instance.

Called by ``dev.cmd`` once the API is up. Waits for ``/health``, signs in as the
demo buyer, and prints every supplier's tokenized form link — which is the one
thing you cannot know without asking the database, because the token is generated
at invitation time.

    uv run python -m scripts.show_links              # used by `dev.cmd start`
    uv run python -m scripts.show_links --timeout 8  # used by `dev.cmd links`
"""

import argparse
import os
import sys
import time

import httpx

API = "http://localhost:8000"
DASHBOARD_URL = "http://localhost:5173"
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
    parser.add_argument(
        "--open",
        action="store_true",
        help="open the buyer dashboard and a live supplier form link in the browser",
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
    supplier_url: str | None = None

    # ------------------------------------------------------- supplier links
    if token:
        headers = {"Authorization": f"Bearer {token}"}

        rfqs = httpx.get(f"{API}/rfqs", headers=headers, timeout=15.0).json()

        if not rfqs:
            print("  No RFQs yet. Load the demo workspace with:   dev.cmd seed")
        else:
            rfq = rfqs[0]

            print(BAR)
            print("  SUPPLIER FORM LINKS  (no login — open on a phone)")
            print(f"  RFQ {rfq['rfq_number']} — {rfq['item_name']}")
            print(BAR)

            invitations = httpx.get(
                f"{API}/rfqs/{rfq['id']}/invitations", headers=headers, timeout=15.0
            ).json()

            # Prefer a supplier who has not submitted yet: that link is the one
            # actually worth clicking, because it is still an open form.
            pending = [i for i in invitations if i["status"] in {"pending", "incomplete"}]

            if pending:
                supplier_url = pending[0]["form_link"]

            for invitation in invitations:
                marker = "  <- the live one to try" if invitation["form_link"] == supplier_url else ""

                print()
                print(f"  {invitation['supplier_name']}  [{invitation['status']}]{marker}")
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
    print("  Re-open the browser:    dev.cmd open")
    print()

    if args.open:
        opened = open_in_browser(DASHBOARD_URL, supplier_url)

        if opened:
            print(f"  Opened {len(opened)} tab(s) in your default browser:")
            for url in opened:
                print(f"    {url}")
        else:
            print("  Could not launch a browser automatically. Open one of the URLs above.")

        print()

    return 0


def open_in_browser(dashboard_url: str, supplier_url: str | None) -> list[str]:
    """Open the two UIs in the default browser. Returns the URLs actually opened.

    This is the difference between "the services are running" and "here is your
    app". The URLs were previously only printed, which is easy to miss in a wall of
    startup output — the launcher now puts the dashboard on screen itself.
    """

    urls = [dashboard_url]

    # The supplier form is the other half of the product and has no navigation from
    # the dashboard, so opening a working link saves hunting for a token in the
    # console output.
    if supplier_url:
        urls.append(supplier_url)

    opened: list[str] = []

    for url in urls:
        try:
            if hasattr(os, "startfile"):  # Windows
                os.startfile(url)  # noqa: S606 - intentional, default browser
            else:  # pragma: no cover - macOS/Linux convenience
                import webbrowser

                if not webbrowser.open(url):
                    continue
            opened.append(url)
        except OSError:
            # A headless or locked-down session: fall back to printing, which the
            # caller does anyway. Never let this fail the command.
            continue

    return opened


if __name__ == "__main__":
    sys.exit(main())
