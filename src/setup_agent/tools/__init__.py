"""Tool registry: JSON schemas the LLM sees + the dispatch table that runs them.

The LLM can ONLY act through what is registered here.
"""

from __future__ import annotations

from ..state import load_profile_text
from .config import account_info, append_powershell_config, configure_git, setup_github
from .packages import (
    check_installed,
    install_background,
    jobs_status,
    rescan,
    search_winget,
    winget_install,
    winget_uninstall,
    winget_upgrade,
)
from .system import run_shell
from .windows import set_windows_registry


def read_profile() -> str:
    """Return the current Setup.md so the model can re-check the plan mid-run."""
    text = load_profile_text()
    return text if text else "No Setup.md exists yet — run the scan first (setup-agent scan)."


FUNCS = {
    "check_installed": check_installed,
    "search_winget": search_winget,
    "install_background": install_background,
    "jobs_status": jobs_status,
    "winget_uninstall": winget_uninstall,
    "winget_upgrade": winget_upgrade,
    "scan_system": rescan,
    "read_profile": read_profile,
    "configure_git": configure_git,
    "account_info": account_info,
    "setup_github": setup_github,
    "append_powershell_config": append_powershell_config,
    "set_windows_registry": set_windows_registry,
    "run_shell": run_shell,
}


def _tool(name: str, description: str, params: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": params,
                "required": required,
            },
        },
    }


TOOLS = [
    _tool(
        "check_installed",
        "Check whether an app or command is already installed on Windows (PATH, Winget). "
        "ALWAYS call this before installing anything.",
        {"name": {"type": "string", "description": "App or tool name, e.g. 'zoom' or 'git'"}},
        ["name"],
    ),
    _tool(
        "search_winget",
        "Search Winget for the exact package ID. Use when unsure of the correct "
        "package ID — never invent IDs.",
        {"query": {"type": "string", "description": "Friendly name to search, e.g. 'whatsapp' or 'vscode'"}},
        ["query"],
    ),
    _tool(
        "winget_uninstall",
        "Uninstall one package with Winget. Removes it from the Setup.md recipe too. "
        "Only when the user explicitly asks to remove something — packages the agent/system "
        "needs (ollama, python, git, winget) are refused.",
        {
            "name": {"type": "string", "description": "Exact Winget package ID or name, e.g. 'Spotify.Spotify'"},
        },
        ["name"],
    ),
    _tool(
        "install_background",
        "THE way to install apps/tools on Windows. Gather EVERYTHING the user wants installed and "
        "call this ONCE — list package names or IDs in 'packages' (zoom, slack, vscode, git, node, python…). "
        "All of them install in parallel in the background; it returns immediately (no waiting), "
        "each notifies + updates Setup.md when done.",
        {
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Package names or Winget IDs to install in background",
            },
        },
        ["packages"],
    ),
    _tool(
        "jobs_status",
        "Report the status of background install jobs started with install_background.",
        {},
        [],
    ),
    _tool(
        "winget_upgrade",
        "Upgrade an already-installed package to its latest version via Winget. Use this for "
        "'update X' / 'upgrade X' requests — NOT winget_install.",
        {
            "name": {"type": "string", "description": "Exact Winget package ID to upgrade, e.g. 'Microsoft.VisualStudioCode'"},
        },
        ["name"],
    ),
    _tool(
        "scan_system",
        "Fresh inventory of the Windows PC: installed packages, runtimes, git identity.",
        {},
        [],
    ),
    _tool(
        "read_profile",
        "Read the current Setup.md profile (the desired state of this machine).",
        {},
        [],
    ),
    _tool(
        "configure_git",
        "Set the global git identity (user.name and user.email).",
        {
            "name": {"type": "string", "description": "Git user.name"},
            "email": {"type": "string", "description": "Git user.email"},
        },
        ["name", "email"],
    ),
    _tool(
        "account_info",
        "Read-only: show the git identity (name + email) and the GitHub username.",
        {},
        [],
    ),
    _tool(
        "setup_github",
        "Set up GitHub on this Windows machine: create SSH key, log in to GitHub CLI (gh), "
        "and register SSH key.",
        {"email": {"type": "string", "description": "email for the SSH key comment (optional)"}},
        [],
    ),
    _tool(
        "append_powershell_config",
        "Append one line to PowerShell $PROFILE (alias, env var, function).",
        {"snippet": {"type": "string", "description": "The exact PowerShell line"}},
        ["snippet"],
    ),
    _tool(
        "set_windows_registry",
        "Set one user-domain Windows Registry setting (Dark mode, Explorer options). "
        "User domain (HKCU) only.",
        {
            "key_path": {"type": "string", "description": "e.g. HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"},
            "value_name": {"type": "string", "description": "e.g. AppsUseLightTheme"},
            "value": {"type": "string", "description": "e.g. 0 for dark mode, 1 for light mode"},
            "value_type": {
                "type": "string",
                "enum": ["string", "dword", "int", "bool"],
                "description": "Registry value type",
            },
        },
        ["key_path", "value_name", "value", "value_type"],
    ),
    _tool(
        "run_shell",
        "Escape hatch: run a PowerShell command when no other tool fits.",
        {
            "command": {"type": "string", "description": "the exact command"},
            "purpose": {"type": "string", "description": "one line: why this command"},
        },
        ["command"],
    ),
]


def dispatch(name: str, arguments: dict) -> str:
    """Run one tool call; always return a string for the model (never raise)."""
    func = FUNCS.get(name)
    if func is None:
        return f"ERROR: unknown tool '{name}'. Available: {', '.join(sorted(FUNCS))}."
    try:
        return str(func(**(arguments or {})))
    except TypeError as exc:
        return f"ERROR: bad arguments for {name}: {exc}"
    except Exception as exc:
        return f"ERROR: {name} failed: {exc}"
