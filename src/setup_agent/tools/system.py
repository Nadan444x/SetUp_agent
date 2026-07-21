"""Escape-hatch tool: run a shell command that no dedicated tool covers.

Goes through the full safety pipeline. Commands outside the allowlist always
prompt the user, even under --yes.
"""

from __future__ import annotations

from ..safety import guarded_run


def run_shell(command: str, purpose: str = "") -> str:
    """Run an arbitrary (guarded) shell command. Use only when no other tool fits."""
    return guarded_run(command, purpose=purpose or "run a shell command")
