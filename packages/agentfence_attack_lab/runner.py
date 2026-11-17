"""Deterministic scenario runner: evaluates fixtures against built-in policies."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentfence_core.models import Decision, PolicyDecision
from agentfence_policy_engine.evaluator import evaluate
from agentfence_policy_engine.policy import Policy

from .scenarios import Scenario, builtin_policy


@dataclass
class ScenarioResult:
    scenario: str
    expected: Decision
    actual: Decision
    passed: bool
    explanation: str
    matched_rule: str | None = None


@dataclass
class ArenaSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def run_scenario(scenario: Scenario) -> ScenarioResult:
    """Evaluate a scenario fixture against the built-in policy named by the fixture.

    The fixture is a *data* description of the input state; nothing is executed.
    """
    policy_def = builtin_policy(scenario.fixture.policy)
    policy = Policy.model_validate({**policy_def, "name": scenario.fixture.policy})
    decision: PolicyDecision = evaluate(policy, scenario.fixture.action, scenario.fixture.resource)
    passed = decision.decision == scenario.expected.decision
    return ScenarioResult(
        scenario=scenario.name,
        expected=scenario.expected.decision,
        actual=decision.decision,
        passed=passed,
        explanation=decision.explanation,
        matched_rule=decision.matched_rule,
    )


def run_scenarios(scenarios: list[Scenario]) -> ArenaSummary:
    """Run all scenarios and return a deterministic summary."""
    summary = ArenaSummary()
    for scenario in scenarios:
        result = run_scenario(scenario)
        summary.results.append(result)
        summary.total += 1
        summary.passed += 1 if result.passed else 0
    summary.failed = summary.total - summary.passed
    return summary
