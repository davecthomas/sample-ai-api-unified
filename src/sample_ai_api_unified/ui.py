"""Console UI primitives: Rich output plus a numbered menu that reads stdin.

Menus deliberately use ``input()`` so the whole app can be driven by piping
choices into stdin (used by scripted verification) as well as interactively.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass(frozen=True)
class MenuOption:
    label: str
    value: Any
    hint: str = ""


def header(title: str, subtitle: str = "") -> None:
    body = f"[bold cyan]{title}[/bold cyan]"
    if subtitle:
        body += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel.fit(body, border_style="cyan"))


def info(message: str) -> None:
    console.print(f"[cyan]•[/cyan] {message}")


def success(message: str) -> None:
    console.print(f"[green]✔[/green] {message}")


def warn(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}")


def error(message: str) -> None:
    console.print(f"[red]✘[/red] {message}")


def read_line(prompt: str) -> str:
    """Read one line from stdin, exiting cleanly on EOF (piped input ran out)."""
    try:
        return input(prompt)
    except EOFError:
        console.print("\n[dim]End of input — exiting.[/dim]")
        raise SystemExit(0) from None


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = read_line(f"{prompt}{suffix}: ").strip()
    return raw or default


def confirm(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = read_line(f"{prompt} ({suffix}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def choose(
    title: str,
    options: Sequence[MenuOption],
    *,
    back_label: str = "Back",
) -> MenuOption | None:
    """Show a numbered menu and return the chosen option, or None for back/quit."""
    while True:
        table = Table(title=title, show_header=False, border_style="blue", min_width=48)
        table.add_column("#", style="bold yellow", justify="right", width=3)
        table.add_column("Option")
        table.add_column("", style="dim")
        for index, option in enumerate(options, start=1):
            table.add_row(str(index), option.label, option.hint)
        table.add_row("0", f"[dim]{back_label}[/dim]", "")
        console.print(table)

        raw = read_line("Select: ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        error(f"Invalid choice: {raw!r}. Enter a number between 0 and {len(options)}.")


def choose_value(title: str, values: Sequence[str], *, back_label: str = "Back") -> str | None:
    """Convenience wrapper for menus whose options are plain strings."""
    picked = choose(title, [MenuOption(v, v) for v in values], back_label=back_label)
    return None if picked is None else str(picked.value)


def multi_toggle(title: str, choices: Sequence[str], selected: set[str]) -> set[str]:
    """Toggle membership of items in ``selected`` until the user is done."""
    current = set(selected)
    while True:
        options = [
            MenuOption(f"[{'x' if choice in current else ' '}] {choice}", choice)
            for choice in choices
        ]
        picked = choose(title, options, back_label="Done")
        if picked is None:
            return current
        value = str(picked.value)
        if value in current:
            current.remove(value)
        else:
            current.add(value)
