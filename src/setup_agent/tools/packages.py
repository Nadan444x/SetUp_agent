"""Tools for finding and installing software via Winget (Windows Package Manager)."""

from __future__ import annotations

import json
import re
import shlex
import shutil
from pathlib import Path

from rich.prompt import Confirm

from ..console import console
from ..jobs import JOBS
from ..safety import get_policy, guarded_batch, guarded_run_argv, refusal_or_none, run_readonly, succeeded
from ..state import record_change, record_removal, scan_system

# Uninstalling these would break the agent itself (its brain / runtime / git / package manager)
_CRITICAL = {"ollama", "git", "python", "pipx", "winget"}

# Cache winget list results once per process
_winget_cache: list[dict] | None = None


def _get_winget_installed() -> list[dict]:
    global _winget_cache
    if _winget_cache is None:
        code, out, _ = run_readonly("winget list --accept-source-agreements", timeout=60)
        items = []
        if code == 0:
            lines = out.splitlines()
            # Find table header start
            header_idx = -1
            for i, l in enumerate(lines):
                if "Id" in l and "Name" in l:
                    header_idx = i
                    break
            if header_idx != -1 and header_idx + 1 < len(lines):
                for line in lines[header_idx + 2:]:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        items.append({"raw": line.strip()})
        _winget_cache = items
    return _winget_cache


def _invalidate_cache() -> None:
    global _winget_cache
    _winget_cache = None


def check_installed(name: str) -> str:
    """Is `name` already on this Windows machine? Checks PATH, Winget, and Program Files."""
    name_clean = name.strip()
    hits: list[str] = []

    exe = shutil.which(name_clean)
    if exe:
        hits.append(f"command `{name_clean}` on PATH at {exe}")

    token_low = name_clean.lower().replace(" ", "")
    code, out, _ = run_readonly(f"winget list --query {shlex.quote(name_clean)}", timeout=30)
    if code == 0 and name_clean.lower() in out.lower():
        hits.append(f"Winget installed package matching `{name_clean}`")

    if hits:
        return f"INSTALLED: {name_clean} — found as: " + "; ".join(hits) + ". Do not reinstall."
    return f"NOT INSTALLED: {name_clean} was not found on PATH or in Winget."


def search_winget(query: str) -> str:
    """Find the exact Winget package ID for a friendly name. Never guess IDs."""
    code, out, err = run_readonly(f"winget search --query {shlex.quote(query)} --accept-source-agreements", timeout=60)
    if code != 0:
        return f"winget search failed: {err.strip() or 'unknown error'}"
    lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("-")]
    if not lines:
        return f"No Winget match for '{query}'. It may need manual installation."
    return "\n".join(lines[:25])


# Common Windows Package Aliases -> Exact Winget Package IDs
_PACKAGE_ALIASES = {
    "vscode": "Microsoft.VisualStudioCode",
    "vs code": "Microsoft.VisualStudioCode",
    "vs-code": "Microsoft.VisualStudioCode",
    "code": "Microsoft.VisualStudioCode",
    "chrome": "Google.Chrome",
    "google chrome": "Google.Chrome",
    "brave": "Brave.Brave",
    "firefox": "Mozilla.Firefox",
    "edge": "Microsoft.Edge",
    "zoom": "Zoom.Zoom",
    "slack": "SlackTechnologies.Slack",
    "whatsapp": "WhatsApp.WhatsApp",
    "telegram": "Telegram.TelegramDesktop",
    "discord": "Discord.Discord",
    "teams": "Microsoft.Teams",
    "git": "Git.Git",
    "node": "OpenJS.NodeJS",
    "nodejs": "OpenJS.NodeJS",
    "python": "Python.Python.3.12",
    "ollama": "Ollama.Ollama",
    "docker": "Docker.DockerDesktop",
    "canva": "Canva.Canva",
    "jq": "jqlang.jq",
    "uv": "astral-sh.uv",
    "go": "GoLang.Go",
    "golang": "GoLang.Go",
    "postman": "Postman.Postman",
    "spotify": "Spotify.Spotify",
    "vlc": "VideoLAN.VLC",
    "7zip": "7zip.7zip",
    "notion": "Notion.Notion",
    "powershell": "Microsoft.PowerShell",
}


def _resolve_package_id(name: str) -> str:
    n = name.strip().lower()
    return _PACKAGE_ALIASES.get(n, name.strip())


def winget_install(name: str) -> str:
    """Install a package using Winget."""
    pkg_id = _resolve_package_id(name)
    argv = [
        "winget", "install", "--id", pkg_id, "--exact",
        "--accept-package-agreements", "--accept-source-agreements", "--source", "winget"
    ]
    result = guarded_run_argv(argv, purpose=f"install {pkg_id}")

    if succeeded(result):
        _invalidate_cache()
        pretty = pkg_id.split(".")[-1] if "." in pkg_id else pkg_id
        item = f"{pretty} (`{pkg_id}`)"
        note = record_change("Applications & Packages (Winget)", item, f"installed package `{pkg_id}`")
        result += f"\n{note}"
    return result


def winget_upgrade(name: str) -> str:
    """Upgrade an already-installed package using Winget."""
    pkg_id = _resolve_package_id(name)
    argv = [
        "winget", "upgrade", "--id", pkg_id, "--exact",
        "--accept-package-agreements", "--accept-source-agreements"
    ]
    result = guarded_run_argv(argv, purpose=f"upgrade {pkg_id}")
    if succeeded(result):
        _invalidate_cache()
        pretty = pkg_id.split(".")[-1] if "." in pkg_id else pkg_id
        item = f"{pretty} (`{pkg_id}`)"
        note = record_change("Applications & Packages (Winget)", item, f"upgraded package `{pkg_id}`")
        result += f"\n{note}"
        from ..notify import notify
        notify("SetUp Agent", f"{pkg_id} upgraded ✓")
    return result


def winget_uninstall(name: str) -> str:
    """Uninstall a package using Winget."""
    pkg_id = _resolve_package_id(name)
    low = pkg_id.lower()
    if any(crit in low for crit in _CRITICAL):
        return (
            f"REFUSED: `{pkg_id}` is required by SetUp Agent or the system (local LLM, Python, Git, Winget). "
            "If you truly want it gone, uninstall it manually."
        )

    argv = ["winget", "uninstall", "--id", pkg_id, "--exact"]
    result = guarded_run_argv(argv, purpose=f"uninstall {pkg_id}")

    if succeeded(result):
        _invalidate_cache()
        note = record_removal(pkg_id, f"uninstalled package `{pkg_id}`")
        result += f"\n{note}"
        from ..notify import notify
        notify("SetUp Agent", f"{pkg_id} uninstalled ✓")
        return result
    return result


def install_background(casks: list[str] | None = None,
                       formulae: list[str] | None = None,
                       packages: list[str] | None = None) -> str:
    """Install packages in the BACKGROUND without blocking. Returns immediately;
    each install reports when it finishes."""
    all_names = (casks or []) + (formulae or []) + (packages or [])
    names = [n.strip() for n in all_names if n.strip()]
    if not names:
        return "Nothing to install — give at least one package name."

    running = JOBS.active_tokens()
    to_start: list[tuple[str, list[str], str, str]] = []
    already: list[str] = []
    seen: set[str] = set()

    for name in names:
        pkg_id = _resolve_package_id(name)
        key = f"winget:{pkg_id.lower()}"
        if key in running or key in seen:
            continue
        seen.add(key)
        argv = [
            "winget", "install", "--id", pkg_id, "--exact",
            "--accept-package-agreements", "--accept-source-agreements", "--source", "winget"
        ]
        to_start.append((pkg_id, argv, "winget", pkg_id))

    if not to_start:
        return "Nothing to install."

    policy = get_policy()
    if policy.dry_run:
        return "DRY-RUN: would start in background: " + ", ".join(t[0] for t in to_start)

    console.print(f"[bold]about to start {len(to_start)} background install(s)[/bold]:")
    for label, *_ in to_start:
        console.print(f"  • {label}")
    if not (policy.bypass or policy.auto_yes):
        if not Confirm.ask("start these in the background?", default=False):
            return "DECLINED: the user said no to background installs."

    started = []
    for label, argv, kind, token in to_start:
        JOBS.spawn_detached(label, argv, kind, token)
        started.append(token)

    return (
        f"Started {len(started)} install(s) in the background via Winget: "
        f"{', '.join(started)}. They keep running on their own — you do NOT need to wait. "
        "Each posts a notification and updates Setup.md when it finishes; `setup-agent jobs` shows status."
    )


def jobs_status() -> str:
    """Report the status of background install jobs."""
    jobs = JOBS.all_spawned()
    if not jobs:
        return "No background jobs this session."
    parts = [f"{j.token or j.label}: {j.status}" for j in jobs]
    return "Background jobs — " + "; ".join(parts)


def rescan() -> str:
    """Fresh read-only inventory of the Windows machine."""
    state = scan_system()
    return (
        f"runtimes: {state.get('runtimes', {})}\n"
        f"git identity: {state.get('git_identity', 'not set')}"
    )
