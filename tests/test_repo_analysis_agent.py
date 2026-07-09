from __future__ import annotations

import asyncio
from pathlib import Path

from oscagent.agent import RepoAnalysisAgent, is_repo_analysis_request
from oscagent.config import Settings
from oscagent.llm import ChatMessage


class RecordingProvider:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    async def chat(self, messages: list[ChatMessage], *, model: str) -> str:
        self.messages = messages
        return f"summary from {model}"


def test_is_repo_analysis_request_matches_english_and_chinese() -> None:
    assert is_repo_analysis_request("analyze repo")
    assert is_repo_analysis_request("分析一下当前项目结构")
    assert not is_repo_analysis_request("hello")


def test_repo_analysis_agent_collects_trace(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Test Repo", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'", encoding="utf-8")
    provider = RecordingProvider()
    settings = Settings(OSCAGENT_MODEL="mock:test")
    agent = RepoAnalysisAgent(provider, settings, tmp_path)

    answer, trace = asyncio.run(agent.analyze("analyze repo"))

    assert answer == "summary from mock:test"
    assert [step.tool_name for step in trace.steps] == [
        "list_files",
        "git_status",
        "read_file",
        "read_file",
    ]
    assert "README.md" in provider.messages[-1].content
