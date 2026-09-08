"""Tests for the Telegram <-> `todo` CLI bridge (pure logic, no network)."""

import json
import subprocess
from unittest.mock import patch

import pytest

from todo.telegram.cli_bridge import (
    TodoCliError,
    format_add_reply,
    format_list_reply,
    is_authorized,
    run_todo_json,
)


def test_is_authorized_matches_allowed_id():
    assert is_authorized(42, 42) is True


def test_is_authorized_rejects_other_id():
    assert is_authorized(1, 42) is False


def test_is_authorized_rejects_when_unconfigured():
    assert is_authorized(42, None) is False


def test_is_authorized_rejects_missing_user():
    assert is_authorized(None, 42) is False


def test_format_add_reply_success():
    msg = format_add_reply(
        {"id": 7, "title": "buy milk", "category": "errand", "priority": "medium"}
    )
    assert "#7" in msg
    assert "buy milk" in msg
    assert "errand" in msg


def test_format_add_reply_error():
    assert "nope" in format_add_reply({"error": "nope"})


def test_format_list_reply_empty():
    assert format_list_reply({"todos": []}) == "Nothing on your list."


def test_format_list_reply_flags_overdue():
    out = format_list_reply(
        {
            "todos": [
                {
                    "id": 1,
                    "title": "pay rent",
                    "due_date": "2026-01-01",
                    "is_overdue": True,
                },
                {"id": 2, "title": "walk dog", "is_overdue": False},
            ]
        }
    )
    lines = out.splitlines()
    assert lines[0].startswith("!")
    assert "pay rent" in lines[0]
    assert lines[1].startswith("-")


def test_run_todo_json_missing_binary_raises():
    with patch("shutil.which", return_value=None), pytest.raises(TodoCliError):
        run_todo_json("ls")


def test_run_todo_json_parses_stdout():
    fake = subprocess.CompletedProcess(
        args=["todo", "ls", "--json"],
        returncode=0,
        stdout=json.dumps({"todos": []}),
        stderr="",
    )
    with (
        patch("shutil.which", return_value="/usr/local/bin/todo"),
        patch("subprocess.run", return_value=fake),
    ):
        assert run_todo_json("ls") == {"todos": []}


def test_run_todo_json_bad_output_raises():
    fake = subprocess.CompletedProcess(
        args=["todo", "ls", "--json"], returncode=1, stdout="not json", stderr="boom"
    )
    with (
        patch("shutil.which", return_value="/usr/local/bin/todo"),
        patch("subprocess.run", return_value=fake),
        pytest.raises(TodoCliError),
    ):
        run_todo_json("ls")


def test_run_todo_json_timeout_raises():
    with (
        patch("shutil.which", return_value="/usr/local/bin/todo"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="todo", timeout=30),
        ),
        pytest.raises(TodoCliError),
    ):
        run_todo_json("ls")
