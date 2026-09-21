"""Demo mode: a read-only, no-account view of the product.

A prospective user should be able to see what the engine actually computes — the
nine weighted criteria, the cap on a quote missing a required licence, GST derived
from a stated rate, the targeted follow-up copy — without creating an account and
without being able to touch anybody's data.

The route table is the guarantee. Everything in this slice is a ``GET``, there is no
database session, and no credential of any kind is accepted, so "view only" is
enforced by what exists rather than by what the front end chooses to hide.
"""

from app.features.demo.router import router

__all__ = ["router"]
