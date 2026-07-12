from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from oscagent.tools import (
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitPushTool,
    GitStatusTool,
    RunLintTool,
    RunTestsTool,
)


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


def test_read_only_development_tools_report_real_results(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert git(tmp_path, "add", "test_sample.py", "module.py").returncode == 0
    assert git(tmp_path, "commit", "-m", "initial").returncode == 0
    (tmp_path / "module.py").write_text("VALUE = 2\n", encoding="utf-8")

    tests = RunTestsTool(tmp_path).execute({})
    lint = RunLintTool(tmp_path).execute({})
    status = GitStatusTool(tmp_path).execute({})
    diff = GitDiffTool(tmp_path).execute({})
    log = GitLogTool(tmp_path).execute({"max_count": 1})

    assert tests.metadata["returncode"] == 0
    assert lint.metadata["returncode"] == 0
    assert "module.py" in status.content
    assert "VALUE = 2" in diff.content
    assert "initial" in log.content


def test_run_tests_reports_failure_without_shell_access(tmp_path: Path) -> None:
    (tmp_path / "test_failure.py").write_text(
        "def test_failure():\n    assert False\n",
        encoding="utf-8",
    )

    result = RunTestsTool(tmp_path).execute({})

    assert result.metadata["returncode"] != 0
    assert "failed" in result.content.lower()
    assert result.metadata["command"][1:3] == ["-m", "pytest"]


def test_git_commit_stages_only_explicit_paths(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("initial", encoding="utf-8")
    assert git(tmp_path, "add", "tracked.txt").returncode == 0
    assert git(tmp_path, "commit", "-m", "initial").returncode == 0
    (tmp_path / "tracked.txt").write_text("changed", encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("do not stage", encoding="utf-8")

    result = GitCommitTool(tmp_path).execute(
        {"message": "phase seven commit", "paths": ["tracked.txt"]}
    )

    assert result.metadata["returncode"] == 0
    assert "phase seven commit" in git(tmp_path, "log", "-1", "--pretty=%s").stdout
    assert "?? unrelated.txt" in git(tmp_path, "status", "--short").stdout


def test_git_commit_rejects_sensitive_and_broad_paths(tmp_path: Path) -> None:
    initialize_repo(tmp_path)
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")

    with pytest.raises(ValueError, match="Sensitive path"):
        GitCommitTool(tmp_path).execute({"message": "bad", "paths": [".env"]})
    with pytest.raises(ValueError, match="explicit paths"):
        GitCommitTool(tmp_path).execute({"message": "bad", "paths": ["."]})


def test_git_push_uses_named_remote_without_force(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()
    assert git(tmp_path, "init", "--bare", str(remote)).returncode == 0
    initialize_repo(repo)
    (repo / "README.md").write_text("test", encoding="utf-8")
    assert git(repo, "add", "README.md").returncode == 0
    assert git(repo, "commit", "-m", "initial").returncode == 0
    assert git(repo, "remote", "add", "origin", str(remote)).returncode == 0

    result = GitPushTool(repo).execute({"remote": "origin", "branch": "main"})

    assert result.metadata["returncode"] == 0
    assert git(remote, "rev-parse", "refs/heads/main").returncode == 0
    assert "--force" not in result.metadata["command"]

    with pytest.raises(ValueError, match="safe configured remote"):
        GitPushTool(repo).execute({"remote": "--force", "branch": "main"})
