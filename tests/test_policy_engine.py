"""Tests for the deterministic policy engine."""

from __future__ import annotations

import pytest
from agentfence_core.models import Decision
from agentfence_policy_engine.evaluator import evaluate
from agentfence_policy_engine.policy import Policy, PolicyValidationError, parse_policy


@pytest.fixture
def policy() -> Policy:
    return parse_policy(
        {
            "name": "test",
            "default": "deny",
            "rules": [
                {"id": "allow-read", "action": "read", "resource": "docs/*", "decision": "allow"},
                {
                    "id": "approval-write",
                    "action": "write",
                    "resource": "*",
                    "decision": "require_approval",
                },
            ],
        },
        "test",
    )


def test_allow_by_rule(policy: Policy) -> None:
    d = evaluate(policy, "read", "docs/readme.md")
    assert d.decision == Decision.ALLOW
    assert d.matched_rule == "allow-read"


def test_require_approval(policy: Policy) -> None:
    d = evaluate(policy, "write", "docs/x.md")
    assert d.decision == Decision.REQUIRE_APPROVAL


def test_deny_by_default(policy: Policy) -> None:
    d = evaluate(policy, "read", "secrets/vault")
    assert d.decision == Decision.DENY
    assert d.matched_rule is None
    assert "default" in d.explanation.lower()


def test_first_match_wins(policy: Policy) -> None:
    p = parse_policy(
        {
            "name": "t",
            "default": "allow",
            "rules": [
                {"id": "deny-all", "action": "*", "resource": "*", "decision": "deny"},
                {"id": "allow-all", "action": "*", "resource": "*", "decision": "allow"},
            ],
        },
        "t",
    )
    assert evaluate(p, "anything", "anywhere").matched_rule == "deny-all"


def test_invalid_policy_rejected() -> None:
    with pytest.raises(PolicyValidationError):
        parse_policy({"name": ""}, "x")


def test_decisions_are_deterministic(policy: Policy) -> None:
    results = {evaluate(policy, "read", "docs/a.md").decision for _ in range(10)}
    assert results == {Decision.ALLOW}
