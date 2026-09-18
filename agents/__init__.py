"""Agent packages.

Two domain agents, kept out of ``backend/`` so the reasoning logic is testable
without a database, a web framework, or a network:

    agents.quote_parser   supplier submission -> normalized, typed quote
    agents.followup       invitation snapshot -> chase / ask / escalate decision

Both accept an optional LLM as a plain async callable and fall back to a
deterministic path when it is absent, so neither package imports a provider SDK.

Concepts adapted from ForgeFlow (MIT, Copyright (c) 2026 JayleeBot) — see the
repository-root ``NOTICE`` for the exact file list.
"""
