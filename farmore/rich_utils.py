"""
Rich formatting utilities for consistent terminal output.

"Beauty is in the eye of the beholder. But colors help." — schema.cx
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Centralized console instance
console = Console()

# Color scheme constants
class Colors:
    """Consistent color scheme for the application."""
    SUCCESS = "green"
    ERROR = "red"
    WARNING = "yellow"
    INFO = "cyan"
    MUTED = "dim"
    HIGHLIGHT = "bold cyan"
    REPO_NAME = "bold blue"


def print_success(message: str, prefix: str = "✅") -> None:
    """Print a success message in green."""
    console.print(f"[{Colors.SUCCESS}]{prefix} {message}[/{Colors.SUCCESS}]")


def print_error(message: str, prefix: str = "❌") -> None:
    """Print an error message in red."""
    console.print(f"[{Colors.ERROR}]{prefix} {message}[/{Colors.ERROR}]")


def print_warning(message: str, prefix: str = "⚠️") -> None:
    """Print a warning message in yellow."""
    console.print(f"[{Colors.WARNING}]{prefix} {message}[/{Colors.WARNING}]")


def print_info(message: str, prefix: str = "ℹ️") -> None:
    """Print an info message in cyan."""
    console.print(f"[{Colors.INFO}]{prefix} {message}[/{Colors.INFO}]")


def print_header(title: str, subtitle: str | None = None) -> None:
    """Print a formatted header with optional subtitle."""
    text = Text()
    text.append(title, style="bold cyan")
    if subtitle:
        text.append(f"\n{subtitle}", style="dim")
    
    panel = Panel(text, border_style="cyan", padding=(0, 1))
    console.print(panel)


def create_summary_table(title: str) -> Table:
    """Create a styled table for summary statistics."""
    table = Table(title=title, show_header=True, header_style="bold cyan", border_style="cyan")
    return table


def create_data_table(title: str | None = None, show_lines: bool = False) -> Table:
    """Create a styled table for data display."""
    table = Table(
        title=title,
        show_header=True,
        header_style="bold blue",
        border_style="blue",
        show_lines=show_lines,
    )
    return table


def print_panel(content: str, title: str | None = None, style: str = "cyan") -> None:
    """Print content in a styled panel."""
    panel = Panel(content, title=title, border_style=style, padding=(0, 1))
    console.print(panel)


def print_section_header(text: str) -> None:
    """Print a section header with visual separation."""
    console.print(f"\n[bold cyan]{'─' * 60}[/bold cyan]")
    console.print(f"[bold cyan]{text}[/bold cyan]")
    console.print(f"[bold cyan]{'─' * 60}[/bold cyan]\n")


def format_repo_name(full_name: str) -> str:
    """Format a repository name with consistent styling."""
    return f"[{Colors.REPO_NAME}]{full_name}[/{Colors.REPO_NAME}]"


def format_count(count: int, label: str, color: str = Colors.INFO) -> str:
    """Format a count with label."""
    return f"[{color}]{count}[/{color}] {label}"


def format_action(action: str, color: str | None = None) -> str:
    """Format an action word with appropriate color."""
    if color is None:
        # Auto-select color based on action
        action_lower = action.lower()
        if action_lower in ["clone", "cloned", "success"]:
            color = Colors.SUCCESS
        elif action_lower in ["update", "updated"]:
            color = Colors.INFO
        elif action_lower in ["skip", "skipped"]:
            color = Colors.WARNING
        elif action_lower in ["fail", "failed", "error"]:
            color = Colors.ERROR
        else:
            color = Colors.INFO
    
    return f"[{color}]{action:8}[/{color}]"


def print_key_value(key: str, value: str | int, key_width: int = 20) -> None:
    """Print a key-value pair with consistent formatting."""
    console.print(f"  [dim]{key:<{key_width}}:[/dim] {value}")


def print_divider(char: str = "─", length: int = 60, style: str = "dim") -> None:
    """Print a visual divider."""
    console.print(f"[{style}]{char * length}[/{style}]")

