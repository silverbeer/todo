"""Thin, testable bridge between the Telegram bot and the `todo` CLI.

The bot shells out to the installed `todo` binary (same as the Claude skill
does) rather than importing repository/enrichment internals directly, so the
CLI stays the single source of truth for add/list behavior.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

TODO_BIN_ENV = "TODO_BIN"
DEFAULT_TODO_BIN = "todo"


class TodoCliError(RuntimeError):
    """Raised when the `todo` CLI is unavailable or returns bad output."""


def _todo_bin() -> str:
    configured = os.getenv(TODO_BIN_ENV, DEFAULT_TODO_BIN)
    resolved = shutil.which(configured)
    if resolved is None:
        raise TodoCliError(
            f"`{configured}` not found on PATH. Set {TODO_BIN_ENV} to its full path."
        )
    return resolved


def run_todo_json(*args: str, timeout: float = 30.0) -> dict:
    """Run `todo <args> --json` and parse stdout as JSON."""
    bin_path = _todo_bin()
    try:
        result = subprocess.run(
            [bin_path, *args, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TodoCliError(f"`todo {' '.join(args)}` timed out") from exc

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TodoCliError(
            f"`todo {' '.join(args)}` returned non-JSON output: {result.stderr.strip()!r}"
        ) from exc


def is_authorized(user_id: int | None, allowed_user_id: int | None) -> bool:
    """A single allowed user id gates the bot; unset id means nobody is allowed."""
    return allowed_user_id is not None and user_id == allowed_user_id


def format_add_reply(data: dict) -> str:
    if error := data.get("error"):
        return f"Couldn't add that: {error}"
    parts = [f"Added #{data['id']}: {data['title']}"]
    if category := data.get("category"):
        parts.append(f"category: {category}")
    if priority := data.get("priority"):
        parts.append(f"priority: {priority}")
    if due := data.get("due_date"):
        parts.append(f"due: {due}")
    return " | ".join(parts)


def format_list_reply(data: dict) -> str:
    if error := data.get("error"):
        return f"Couldn't list: {error}"
    todos = data.get("todos", [])
    if not todos:
        return "Nothing on your list."
    lines = []
    for t in todos:
        marker = "!" if t.get("is_overdue") else "-"
        due = f" (due {t['due_date']})" if t.get("due_date") else ""
        lines.append(f"{marker} #{t['id']} {t['title']}{due}")
    return "\n".join(lines)
