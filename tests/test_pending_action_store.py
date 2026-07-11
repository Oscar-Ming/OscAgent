from __future__ import annotations

from pathlib import Path

from oscagent.actions import PendingActionStore, PendingOperation


def test_create_and_get_pending_action(tmp_path: Path) -> None:
    store = PendingActionStore(tmp_path / "actions.db")

    action = store.create(
        "Create docs",
        [PendingOperation(tool_name="create_directory", arguments={"path": "docs"})],
    )

    loaded = store.get(action.id)
    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.operations[0].tool_name == "create_directory"


def test_mark_pending_action_status(tmp_path: Path) -> None:
    store = PendingActionStore(tmp_path / "actions.db")
    action = store.create(
        "Create docs",
        [PendingOperation(tool_name="create_directory", arguments={"path": "docs"})],
    )

    assert store.mark_status(action.id, "executed")
    assert store.get(action.id).status == "executed"  # type: ignore[union-attr]


def test_list_pending_actions(tmp_path: Path) -> None:
    store = PendingActionStore(tmp_path / "actions.db")
    first = store.create(
        "Create docs",
        [PendingOperation(tool_name="create_directory", arguments={"path": "docs"})],
    )
    second = store.create(
        "Create notes",
        [PendingOperation(tool_name="create_directory", arguments={"path": "notes"})],
    )
    store.mark_status(first.id, "cancelled")

    pending = store.list_pending()

    assert [action.id for action in pending] == [second.id]
