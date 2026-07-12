from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from oscagent.actions import PendingActionStore
from oscagent.agent import DevelopmentWorkflowAgent
from oscagent.config import Settings
from oscagent.discord_core import DiscordCommandHandler
from oscagent.llm import ChatMessage
from oscagent.memory import MemoryStore


class PlanProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.messages: list[ChatMessage] = []

    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        self.messages = messages
        return json.dumps(self.payload)


def git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def initialize_repo(repo: Path) -> None:
    assert git(repo, "init", "-b", "main").returncode == 0
    assert git(repo, "config", "user.name", "OscAgent Test").returncode == 0
    assert git(repo, "config", "user.email", "oscagent@example.test").returncode == 0


def test_workflow_blocks_commit_when_tests_fail(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "test_failure.py").write_text(
        "def test_failure():\n    assert False\n",
        encoding="utf-8",
    )
    provider = PlanProvider(
        {
            "description": "Test then commit",
                "operations": [
                    {"tool_name": "run_tests", "arguments": {}},
                    {"tool_name": "run_lint", "arguments": {}},
                    {
                    "tool_name": "git_commit",
                    "arguments": {"message": "should not happen", "paths": ["test_failure.py"]},
                },
            ],
        }
    )
    settings = Settings(OSCAGENT_MODEL="mock:phase7")

    result = asyncio.run(
        DevelopmentWorkflowAgent(provider, settings, tmp_path).run(
            "运行测试，通过后提交代码"
        )
    )

    assert result.blocked_reason == "run_tests failed; write operations were blocked."
    assert result.pending_operations == []
    assert git(tmp_path, "log", "--oneline").stdout == ""


def test_workflow_rejects_commit_when_model_omits_requested_checks(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    provider = PlanProvider(
        {
            "description": "Incomplete commit plan",
            "operations": [
                {
                    "tool_name": "git_commit",
                    "arguments": {"message": "incomplete", "paths": ["app.py"]},
                }
            ],
        }
    )
    settings = Settings(OSCAGENT_MODEL="mock:phase7")

    with pytest.raises(ValueError, match="must run tests first"):
        asyncio.run(
            DevelopmentWorkflowAgent(provider, settings, tmp_path).run(
                "运行测试，通过后提交代码"
            )
        )


def test_workflow_rejects_commit_and_push_in_one_plan(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    provider = PlanProvider(
        {
            "description": "Unsafe combined Git write",
            "operations": [
                {
                    "tool_name": "git_commit",
                    "arguments": {"message": "combined", "paths": ["app.py"]},
                },
                {
                    "tool_name": "git_push",
                    "arguments": {"remote": "origin", "branch": "main"},
                },
            ],
        }
    )
    settings = Settings(OSCAGENT_MODEL="mock:phase7")

    with pytest.raises(ValueError, match="only one Git write operation"):
        asyncio.run(
            DevelopmentWorkflowAgent(provider, settings, tmp_path).run(
                "提交代码并推送到GitHub"
            )
        )


def test_discord_workflow_commits_only_after_confirmation(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    assert git(tmp_path, "add", "app.py", "test_sample.py").returncode == 0
    assert git(tmp_path, "commit", "-m", "initial").returncode == 0
    (tmp_path / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    provider = PlanProvider(
        {
            "description": "Commit app.py after checks",
            "operations": [
                {"tool_name": "run_tests", "arguments": {}},
                {"tool_name": "run_lint", "arguments": {}},
                {
                    "tool_name": "git_commit",
                    "arguments": {"message": "phase seven verification", "paths": ["app.py"]},
                },
            ],
        }
    )
    settings = Settings(OSCAGENT_MODEL="mock:phase7", OSCAGENT_DB_PATH=tmp_path / "agent.db")
    handler = DiscordCommandHandler(
        provider,
        settings,
        MemoryStore(settings.db_path),
        PendingActionStore(settings.db_path),
        tmp_path,
    )

    pending = asyncio.run(handler.handle_ask("运行代码检查，通过后提交代码"))

    assert "Pending action pa_1" in pending.content
    assert "`git_commit`" in pending.content
    assert "initial" in git(tmp_path, "log", "-1", "--pretty=%s").stdout

    executed = asyncio.run(handler.handle_ask("确认执行 pa_1"))

    assert "Executed pa_1" in executed.content
    assert "phase seven verification" in git(tmp_path, "log", "-1", "--pretty=%s").stdout


def test_discord_rejects_arbitrary_shell_request(tmp_path: Path) -> None:
    provider = PlanProvider({"description": "unused", "operations": []})
    settings = Settings(OSCAGENT_MODEL="mock:phase7", OSCAGENT_DB_PATH=tmp_path / "agent.db")
    handler = DiscordCommandHandler(
        provider,
        settings,
        MemoryStore(settings.db_path),
        PendingActionStore(settings.db_path),
        tmp_path,
    )

    response = asyncio.run(handler.handle_ask("运行 powershell 命令删除所有文件"))

    assert "Arbitrary shell commands are not supported" in response.content
    assert provider.messages == []


def test_discord_pushes_only_after_separate_confirmation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    assert git(tmp_path, "init", "--bare", str(remote)).returncode == 0
    initialize_repo(repo)
    (repo / "README.md").write_text("phase seven", encoding="utf-8")
    assert git(repo, "add", "README.md").returncode == 0
    assert git(repo, "commit", "-m", "ready to push").returncode == 0
    assert git(repo, "remote", "add", "origin", str(remote)).returncode == 0
    provider = PlanProvider(
        {
            "description": "Push main to origin",
            "operations": [
                {
                    "tool_name": "git_push",
                    "arguments": {"remote": "origin", "branch": "main"},
                }
            ],
        }
    )
    settings = Settings(OSCAGENT_MODEL="mock:phase7", OSCAGENT_DB_PATH=repo / "agent.db")
    handler = DiscordCommandHandler(
        provider,
        settings,
        MemoryStore(settings.db_path),
        PendingActionStore(settings.db_path),
        repo,
    )

    pending = asyncio.run(handler.handle_ask("把当前commit推送到GitHub"))

    assert "Pending action pa_1" in pending.content
    assert "`git_push`" in pending.content
    assert git(remote, "rev-parse", "refs/heads/main").returncode != 0

    executed = asyncio.run(handler.handle_ask("确认执行 pa_1"))

    assert "Executed pa_1" in executed.content
    assert git(remote, "rev-parse", "refs/heads/main").returncode == 0
