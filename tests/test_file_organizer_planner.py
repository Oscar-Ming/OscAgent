from __future__ import annotations

from pathlib import Path

import pytest

from oscagent.planner import FileOrganizerPlanner


def test_file_organizer_plans_matching_extension_moves(tmp_path: Path) -> None:
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "scratch" / "b.md").write_text("b", encoding="utf-8")

    plan = FileOrganizerPlanner(tmp_path).plan("organize txt files in scratch to archive")

    assert plan is not None
    assert plan.matched_count == 1
    assert plan.operations[0].tool_name == "move_file"
    assert plan.operations[0].arguments == {
        "source": "scratch/a.txt",
        "destination": "archive/a.txt",
    }


def test_file_organizer_accepts_chinese_organize_request(tmp_path: Path) -> None:
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "a.txt").write_text("a", encoding="utf-8")

    plan = FileOrganizerPlanner(tmp_path).plan(
        "\u628a scratch \u91cc\u7684 txt \u6587\u4ef6\u6574\u7406\u5230 archive"
    )

    assert plan is not None
    assert plan.operations[0].arguments["destination"] == "archive/a.txt"


def test_file_organizer_returns_empty_plan_when_no_files_match(tmp_path: Path) -> None:
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "a.md").write_text("a", encoding="utf-8")

    plan = FileOrganizerPlanner(tmp_path).plan("organize txt files in scratch to archive")

    assert plan is not None
    assert plan.matched_count == 0
    assert plan.operations == []


def test_file_organizer_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside the workspace"):
        FileOrganizerPlanner(tmp_path).plan("organize txt files in ../outside to archive")
