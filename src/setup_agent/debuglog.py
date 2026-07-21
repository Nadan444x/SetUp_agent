"""Per-session log file so you can watch what the agent does in real time.

Start a session at the top of a run/chat; every model turn and tool call is appended
with a timestamp. Tail it live:  tail -f ~/.setup-agent/logs/session-<ts>.log
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".setup-agent" / "logs"
_session_file: Path | None = None


def start_session(goal: str) -> Path:
    global _session_file
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    _session_file = LOG_DIR / f"session-{ts}.log"
    log(f"=== SESSION START · {goal} ===")
    return _session_file


def log(message: str) -> None:
    if _session_file is None:
        return
    try:
        with _session_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%H:%M:%S}  {message}\n")
    except OSError:
        pass  # logging must never break a run
