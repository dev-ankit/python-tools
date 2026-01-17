"""User prompts and confirmations."""

import os
import sys
from typing import Optional


def should_prompt() -> bool:
    """Check if we should prompt the user (or auto-accept for scripting)."""
    return os.environ.get("WT_NO_PROMPT", "0") != "1"


def confirm(message: str, default: bool = False) -> bool:
    """
    Prompt user for yes/no confirmation.

    Args:
        message: Message to display
        default: Default value if WT_NO_PROMPT is set

    Returns:
        True if user confirms, False otherwise
    """
    if not should_prompt():
        return default

    suffix = "[y/N]" if not default else "[Y/n]"
    prompt = f"{message} {suffix}: "

    try:
        response = input(prompt).strip().lower()
        if not response:
            return default
        return response in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()  # New line after ^C
        return False


def prompt_choice(message: str, choices: list, default: Optional[str] = None) -> Optional[str]:
    """
    Prompt user to choose from a list of options.

    Args:
        message: Message to display
        choices: List of valid choices
        default: Default choice if WT_NO_PROMPT is set

    Returns:
        Selected choice or None if cancelled
    """
    if not should_prompt():
        return default

    print(message)
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")

    try:
        response = input("Enter choice (1-{}): ".format(len(choices))).strip()
        if not response:
            return default

        try:
            idx = int(response) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass

        return None
    except (KeyboardInterrupt, EOFError):
        print()
        return None


def error(message: str, exit_code: Optional[int] = None):
    """
    Print an error message and optionally exit.

    Args:
        message: Error message
        exit_code: If provided, exit with this code
    """
    print(f"Error: {message}", file=sys.stderr)
    if exit_code is not None:
        sys.exit(exit_code)


def warning(message: str):
    """Print a warning message."""
    print(f"Warning: {message}", file=sys.stderr)


def info(message: str):
    """Print an info message."""
    print(message)


def success(message: str):
    """Print a success message."""
    print(f"✓ {message}")
