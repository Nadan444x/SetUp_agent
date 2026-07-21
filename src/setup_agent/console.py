"""Shared Rich console + small rendering helpers.
"""

from __future__ import annotations

import sys
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def rule(title: str) -> None:
    console.rule(f"[bold cyan]{title}")


def info(message: str) -> None:
    console.print(f"[cyan]›[/cyan] {message}")


def success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")


def warn(message: str) -> None:
    console.print(f"[bold yellow]![/bold yellow] {message}")


def error(message: str) -> None:
    console.print(f"[bold red]✗[/bold red] {message}")


def assistant_text(message: str) -> None:
    """Render a plain-language reply from the model."""
    if message.strip():
        console.print(Panel(Text(message.strip()), title="🧠 agent", border_style="magenta"))


def tool_call(name: str, arguments: dict) -> None:
    """Show what the model is asking to do, before we run it."""
    args = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    console.print(f"[bold blue]→ tool[/bold blue] [white]{name}[/white]([dim]{args}[/dim])")


def tool_result(name: str, result: str, ok: bool = True) -> None:
    """Show the result we are feeding back to the model."""
    style = "green" if ok else "red"
    body = result if len(result) < 1500 else result[:1500] + "\n… (truncated)"
    console.print(Panel(body, title=f"result · {name}", border_style=style, expand=False))


def command_preview(command: str) -> None:
    """Pretty-print a shell command the agent is about to run."""
    console.print(Syntax(command, "powershell", theme="ansi_dark", word_wrap=True))


def status_table(rows: list[tuple[str, bool, str]], title: str = "doctor") -> Table:
    """Build a green/red preflight table. rows = (label, ok?, hint)."""
    table = Table(title=title, title_style="bold cyan", show_lines=False)
    table.add_column("check", style="white", no_wrap=True)
    table.add_column("status", justify="center")
    table.add_column("detail / fix", style="dim")
    for label, ok, hint in rows:
        badge = "[bold green]✓ ok[/bold green]" if ok else "[bold red]✗ missing[/bold red]"
        table.add_row(label, badge, hint)
    return table
