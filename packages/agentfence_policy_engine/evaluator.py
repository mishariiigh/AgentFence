"""Deterministic policy evaluation with explicit explanations."""

from __future__ import annotations

import fnmatch

from agentfence_core.models import Decision, PolicyDecision

from .policy import Policy


def evaluate(policy: Policy, action: str, resource: str) -> PolicyDecision:
    """Evaluate ``action`` on ``resource`` against ``policy``.

    First matching rule wins; otherwise the policy default applies.
    The decision is fully deterministic — no LLM is involved.
    """
    for rule in policy.rules:
        if _action_matches(rule.action, action) and _resource_matches(rule.resource, resource):
            verb = {
                Decision.ALLOW: "Allowed",
                Decision.DENY: "Denied",
                Decision.REQUIRE_APPROVAL: "Requires approval",
            }[rule.decision]
            return PolicyDecision(
                decision=rule.decision,
                matched_rule=rule.id,
                explanation=(
                    f"{verb} '{action}' on '{resource}' by rule '{rule.id}' "
                    f"(action={rule.action}, resource={rule.resource})."
                ),
            )
    return PolicyDecision(
        decision=policy.default,
        matched_rule=None,
        explanation=(
            f"No rule matched '{action}' on '{resource}'; "
            f"policy default '{policy.default.value}' applied."
        ),
    )


def _action_matches(pattern: str, action: str) -> bool:
    return pattern == "*" or fnmatch.fnmatch(action.lower(), pattern.lower())


def _resource_matches(pattern: str, resource: str) -> bool:
    return pattern == "*" or fnmatch.fnmatch(resource.lower(), pattern.lower())
