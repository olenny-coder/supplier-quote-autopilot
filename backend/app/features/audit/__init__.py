"""Audit log — the append-only record of what happened in a workspace.

See ``model.py`` for why this exists as a log rather than a state table, and
``service.py`` for why the writes happen in the domain services rather than in a
middleware. Reads and the CSV export are in ``router.py``.
"""
