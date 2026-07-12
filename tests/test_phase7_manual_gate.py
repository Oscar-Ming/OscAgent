from __future__ import annotations

from pathlib import Path

FAILURE_GATE = Path(__file__).parents[1] / ".phase7_failure_gate"


def test_phase7_failure_gate_is_disabled() -> None:
    assert not FAILURE_GATE.exists(), (
        "Intentional Phase 7 verification failure: remove .phase7_failure_gate "
        "before testing the successful commit workflow."
    )


def test_phase7_success_case() -> None:
    assert 2 + 2 == 4
