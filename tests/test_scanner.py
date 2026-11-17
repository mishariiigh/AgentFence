"""Tests for the read-only scanner."""

from __future__ import annotations

import json
from pathlib import Path

from agentfence_scanner.engine import ScanError, scan_path


def test_scan_detects_risky_settings(settings_json: Path) -> None:
    result = scan_path(settings_json)
    ids = {f.id for f in result.findings}
    assert any(f.id.endswith("ALLOW_UNSAFE_PERMISSIONS") for f in result.findings)
    assert "AF-AUTO_APPROVE_ALL" in ids
    assert "AF-SUSPICIOUS-INSTRUCTION" in ids
    assert result.files_inspected == 1


def test_scan_clean_file(clean_json: Path) -> None:
    result = scan_path(clean_json)
    assert result.findings == []


def test_scan_detects_secret_with_redaction(tmp_path: Path) -> None:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"token": "sk-proj-abcdefghij1234567890ABCD"}), encoding="utf-8")
    result = scan_path(p)
    secret_findings = [f for f in result.findings if f.category == "secrets"]
    assert secret_findings
    assert all(
        "sk-proj-abcdefghij1234567890ABCD" not in (f.evidence or "") for f in secret_findings
    )


def test_scan_missing_target_raises(tmp_path: Path) -> None:
    try:
        scan_path(tmp_path / "nope")
    except ScanError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("expected ScanError")


def test_scan_is_recursive_and_ignores_node_modules(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "settings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "settings.json").write_text("{}", encoding="utf-8")
    result = scan_path(tmp_path)
    assert result.files_inspected == 1
