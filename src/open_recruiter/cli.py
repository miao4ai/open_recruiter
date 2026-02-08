"""Interactive terminal UI for Open Recruiter."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

from open_recruiter.config import load_config
from open_recruiter.orchestrator import Orchestrator

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
})

console = Console(theme=custom_theme)

BANNER = r"""
  ___                   ____                      _ _
 / _ \ _ __   ___ _ __ |  _ \ ___  ___ _ __ _   _(_) |_ ___ _ __
| | | | '_ \ / _ \ '_ \| |_) / _ \/ __| '__| | | | | __/ _ \ '__|
| |_| | |_) |  __/ | | |  _ <  __/ (__| |  | |_| | | ||  __/ |
 \___/| .__/ \___|_| |_|_| \_\___|\___|_|   \__,_|_|\__\___|_|
      |_|
"""


def main() -> None:
    """Entry point for the Open Recruiter CLI."""
    console.print(Panel(BANNER, title="Open Recruiter v0.1.0", border_style="cyan"))
    console.print(
        "[info]AI-powered recruitment automation agent.[/info]\n"
        "Type your request, or try one of these:\n"
        "  • Paste a job description to get started\n"
        "  • Paste candidate resumes to add them to the pipeline\n"
        "  • Type [bold]match[/bold] to rank candidates\n"
        "  • Type [bold]status[/bold] to view the pipeline\n"
        "  • Type [bold]quit[/bold] or [bold]exit[/bold] to leave\n"
    )

    config = load_config()

    # Validate API key
    if config.llm_provider == "anthropic" and not config.anthropic_api_key:
        console.print("[error]ANTHROPIC_API_KEY not set. Copy env.example to .env and fill in your key.[/error]")
        sys.exit(1)
    if config.llm_provider == "openai" and not config.openai_api_key:
        console.print("[error]OPENAI_API_KEY not set. Copy env.example to .env and fill in your key.[/error]")
        sys.exit(1)

    orch = Orchestrator(config)

    try:
        _loop(orch)
    except KeyboardInterrupt:
        console.print("\n[info]Goodbye![/info]")
    finally:
        orch.close()


def _loop(orch: Orchestrator) -> None:
    """Main REPL loop."""
    while True:
        try:
            user_input = console.input("\n[bold green]You>[/bold green] ").strip()
        except EOFError:
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[info]Goodbye![/info]")
            break

        console.print()
        try:
            response = orch.handle(user_input)
            console.print(f"\n[bold cyan]🤖 Open Recruiter>[/bold cyan] {response}")
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")


if __name__ == "__main__":
    main()
