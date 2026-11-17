"""Tests for the Attack Lab scenario runner."""

from __future__ import annotations

from pathlib import Path

from agentfence_attack_lab.runner import run_scenarios
from agentfence_attack_lab.scenarios import ScenarioError, load_scenarios


def test_load_builtin_scenarios() -> None:
    scenarios = load_scenarios([Path("benchmarks/scenarios")])
    assert len(scenarios) >= 4
    names = {s.name for s in scenarios}
    assert "write-should-deny" in names


def test_runner_passes_baseline() -> None:
    scenarios = load_scenarios([Path("benchmarks/scenarios")])
    summary = run_scenarios(scenarios)
    assert summary.total == len(scenarios)
    assert summary.failed == 0
    assert summary.pass_rate == 1.0


def test_invalid_scenario_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("name: broken\n", encoding="utf-8")  # missing fixture/expected
    try:
        load_scenarios([p])
    except ScenarioError:
        pass
    else:
        raise AssertionError("expected ScenarioError")


def test_runner_is_deterministic() -> None:
    scenarios = load_scenarios([Path("benchmarks/scenarios")])
    a = run_scenarios(scenarios)
    b = run_scenarios(scenarios)
    assert [r.passed for r in a.results] == [r.passed for r in b.results]
