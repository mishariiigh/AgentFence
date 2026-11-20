"""Tests for the Arena and Policies API routes."""

from __future__ import annotations

from pathlib import Path

from agentfence_api.app import create_app
from agentfence_api.security import TOKEN_HEADER, SecurityConfig
from fastapi.testclient import TestClient

POLICY_YAML = """
name: test-policy
default: deny
rules:
  - id: allow-read-docs
    action: read
    resource: "docs/*"
    decision: allow
"""


def _client(tmp_path: Path) -> TestClient:
    sec = SecurityConfig(token="tok", rate_limit=1000)
    app = create_app(db_path=tmp_path / "db.sqlite", security=sec)
    client = TestClient(app)
    original_post = client.post

    def post(path: str, **kwargs: object) -> object:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers[TOKEN_HEADER] = "tok"
        return original_post(path, headers=headers, **kwargs)  # type: ignore[arg-type]

    client.post = post  # type: ignore[method-assign]
    return client


# ---------------------------------------------------------------------------
# Arena
# ---------------------------------------------------------------------------


def test_arena_scenarios_discovered(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/api/v1/arena/scenarios")
    assert r.status_code == 200
    scenarios = r.json()
    names = {s["name"] for s in scenarios}
    assert "write-should-deny" in names
    first = scenarios[0]
    assert {"name", "description", "tags", "expected_decision"} <= set(first)


def test_arena_run_all_scenarios(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/arena/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 4
    assert body["passed"] == body["total"]  # baseline suite is all-pass
    assert body["score"] == 1.0
    assert all(res["passed"] for res in body["results"])


def test_arena_run_subset_and_failure_detail(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/api/v1/arena/run", json={"scenario_ids": ["read-allowed-in-read-only-policy"]}
    )
    body = r.json()
    assert body["total"] == 1
    result = body["results"][0]
    assert result["scenario"] == "read-allowed-in-read-only-policy"
    assert result["expected"] == "allow" and result["actual"] == "allow"
    assert result["explanation"]  # deterministic explanation present


def test_arena_run_invalid_scenario_id(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/api/v1/arena/run", json={"scenario_ids": ["no-such-scenario"]})
    assert r.status_code == 422
    assert "unknown scenario" in r.json()["detail"]


def test_arena_run_persisted_and_history(tmp_path: Path) -> None:
    client = _client(tmp_path)
    run_id = client.post("/api/v1/arena/run", json={}).json()["run_id"]
    hist = client.get("/api/v1/arena/runs").json()
    assert hist["total"] == 1
    assert hist["runs"][0]["run_id"] == run_id
    detail = client.get(f"/api/v1/arena/runs/{run_id}").json()
    assert detail["passed"] == detail["scenario_count"]
    assert len(detail["results"]) == detail["scenario_count"]


def test_arena_unknown_run_404(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/api/v1/arena/runs/missing").status_code == 404


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


def test_policies_list_contains_example(tmp_path: Path) -> None:
    policies = _client(tmp_path).get("/api/v1/policies").json()["policies"]
    example = [p for p in policies if p["file"] == "example.yaml"]
    assert example and example[0]["valid"] is True
    assert example[0]["rule_count"] >= 3
    assert any(r["decision"] == "require_approval" for r in example[0]["rules"])


def test_policy_validate_ok_and_invalid(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ok = client.post("/api/v1/policies/validate", json={"content": POLICY_YAML}).json()
    assert ok == {"valid": True, "problems": []}
    bad = client.post("/api/v1/policies/validate", json={"content": "name: [unclosed"}).json()
    assert bad["valid"] is False
    assert bad["problems"]


def test_policy_validate_empty_rejected(tmp_path: Path) -> None:
    r = _client(tmp_path).post("/api/v1/policies/validate", json={"content": ""})
    assert r.status_code == 422


def test_policy_evaluate_allow_deny_approval(tmp_path: Path) -> None:
    client = _client(tmp_path)
    content = POLICY_YAML + (
        "  - id: approval-writes\n"
        "    action: write\n"
        "    resource: '*'\n"
        "    decision: require_approval\n"
        "  - id: deny-secrets\n"
        "    action: read\n"
        "    resource: 'secrets/*'\n"
        "    decision: deny\n"
    )
    allow = client.post(
        "/api/v1/policies/evaluate",
        json={"content": content, "action": "read", "resource": "docs/a.md"},
    ).json()
    assert allow["decision"] == "allow"
    assert allow["matched_rule"] == "allow-read-docs"
    assert "allow-read-docs" in allow["explanation"]

    approval = client.post(
        "/api/v1/policies/evaluate",
        json={"content": content, "action": "write", "resource": "docs/a.md"},
    ).json()
    assert approval["decision"] == "require_approval"

    deny = client.post(
        "/api/v1/policies/evaluate",
        json={"content": content, "action": "read", "resource": "secrets/x"},
    ).json()
    assert deny["decision"] == "deny"


def test_policy_evaluate_default_deny_when_no_match(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/api/v1/policies/evaluate",
        json={"content": POLICY_YAML, "action": "exec", "resource": "anything"},
    ).json()
    assert r["decision"] == "deny"
    assert r["matched_rule"] is None
    assert "default" in r["explanation"]


def test_policy_evaluate_invalid_policy_never_allows(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/api/v1/policies/evaluate",
        json={"content": "name: [broken", "action": "read", "resource": "docs/*"},
    )
    assert r.status_code == 422
    # decision must not be recorded as an allow
    hist = _client(tmp_path).get("/api/v1/policies/history").json()["evaluations"]
    assert all(e["decision"] != "allow" for e in hist)


def test_policy_evaluate_by_name_and_history(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/api/v1/policies/evaluate",
        json={"name": "example-policy", "action": "read", "resource": "docs/a.md"},
    )
    assert r.status_code == 200
    assert r.json()["policy"] == "example-policy"
    hist = client.get("/api/v1/policies/history").json()
    assert hist["evaluations"]
    entry = hist["evaluations"][0]
    assert {"evaluation_id", "created_at", "policy_name", "action", "decision"} <= set(entry)


def test_policy_evaluate_unknown_name_404(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/api/v1/policies/evaluate",
        json={"name": "ghost", "action": "read", "resource": "docs/*"},
    )
    assert r.status_code == 404


def test_policy_evaluate_name_and_content_mutually_exclusive(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/api/v1/policies/evaluate",
        json={"name": "a", "content": POLICY_YAML, "action": "read", "resource": "docs/*"},
    )
    assert r.status_code == 422


def test_policy_evaluate_neither_name_nor_content(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/api/v1/policies/evaluate",
        json={"action": "read", "resource": "docs/*"},
    )
    assert r.status_code == 422


def test_policy_inline_yaml_untouched_on_disk(tmp_path: Path) -> None:
    """Inline policy content must not be written to the filesystem."""
    client = _client(tmp_path)
    client.post(
        "/api/v1/policies/evaluate",
        json={"content": POLICY_YAML, "action": "read", "resource": "docs/*"},
    )
    assert not (tmp_path / "policies").exists()


def test_policy_evaluation_persists_across_restart(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    client = _client(tmp_path)
    client.post(
        "/api/v1/policies/evaluate",
        json={"content": POLICY_YAML, "action": "read", "resource": "docs/a.md"},
    )
    # new app instance over the same database
    sec = SecurityConfig(token="tok", rate_limit=1000)
    client2 = TestClient(create_app(db_path=db, security=sec))
    hist = client2.get("/api/v1/policies/history").json()["evaluations"]
    assert len(hist) == 1


def test_policy_yaml_dump_safe(tmp_path: Path) -> None:
    """Validation endpoint must handle arbitrary YAML safely."""
    content = "!!python/object/apply:os.system ['echo hacked']"
    r = _client(tmp_path).post("/api/v1/policies/validate", json={"content": content})
    assert r.status_code == 200
    assert r.json()["valid"] is False
