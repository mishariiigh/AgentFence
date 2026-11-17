"""AgentFence command-line interface.

Run `agentfence --help` for available commands.
All commands are local-first and read-only with respect to scanned targets.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from agentfence_attack_lab.runner import run_scenarios
from agentfence_attack_lab.scenarios import ScenarioError, load_scenarios
from agentfence_core.models import ScanResult
from agentfence_flight_recorder.recorder import FlightRecorder
from agentfence_mcp_inspector.inspector import McpInspectError, inspect_mcp_config
from agentfence_policy_engine.evaluator import evaluate
from agentfence_policy_engine.policy import PolicyValidationError, load_policy
from agentfence_report_generator.reports import save_report
from agentfence_risk_engine.scoring import risk_label, score_findings
from agentfence_scanner.engine import ScanError, scan_path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="agentfence",
    help="AgentFence — AI Agent Security Engineering Platform. Scan. Test. Protect. Monitor.",
    no_args_is_help=True,
    add_completion=False,
)
policy_app = typer.Typer(name="policy", help="Policy file commands.")
mcp_app = typer.Typer(name="mcp", help="MCP server configuration inspection (read-only).")
app.add_typer(policy_app)
app.add_typer(mcp_app)

console = Console()
err_console = Console(stderr=True)

BANNER = (
    "[bold cyan]AgentFence[/] — AI Agent Security Engineering Platform\n"
    "[dim]Scan. Test. Protect. Monitor. (local-first, read-only, no telemetry)[/]"
)


def _fail(message: str) -> None:
    err_console.print(f"[bold red]Error:[/] {message}")
    raise typer.Exit(code=2)


@app.command()
def init() -> None:
    """Initialize an AgentFence workspace in the current directory."""
    created = []
    directories = (
        ".agentfence",
        ".agentfence/scenarios",
        ".agentfence/policies",
        ".agentfence/reports",
    )
    for directory in directories:
        p = Path(directory)
        if not p.exists():
            p.mkdir(parents=True)
            created.append(directory)
    example_policy = Path(".agentfence/policies/policy.yaml")
    if not example_policy.exists():
        example_policy.write_text(
            "name: workspace-policy\n"
            "default: deny\n"
            "rules:\n"
            "  - id: allow-read\n"
            "    action: read\n"
            "    resource: '*'\n"
            "    decision: allow\n",
            encoding="utf-8",
        )
        created.append(str(example_policy))
    FlightRecorder().record("init", {"created": created})
    console.print(BANNER)
    created_str = ", ".join(created) or "nothing (already present)"
    console.print(f"[green]Initialized AgentFence workspace.[/] Created: {created_str}")


@app.command()
def scan(
    path: Path = typer.Argument(  # noqa: B008
        ..., exists=True, readable=True, help="File or directory to scan."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output results as JSON."),
    report: Path | None = typer.Option(  # noqa: B008
        None, "--report", help="Save a JSON report to this path."
    ),
) -> None:
    """Statically scan AI agent configuration files (read-only, never executes them)."""
    try:
        result = scan_path(path)
    except ScanError as exc:
        _fail(str(exc))
        return
    FlightRecorder().record("scan", {"target": str(path), "findings": len(result.findings)})
    if output_json:
        console.print_json(json.dumps(result.model_dump(mode="json")))
    else:
        _print_scan(result)
    if report:
        out = save_report(result, report)
        console.print(f"[green]Report saved:[/] {out}")


@app.command()
def arena(
    scenarios: list[Path] = typer.Argument(  # noqa: B008
        None, help="Scenario files or directories (default: benchmarks/scenarios)."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output the summary as JSON."),
) -> None:
    """Run declarative attack-simulation scenarios (no agents launched, no payloads run)."""
    paths = scenarios or [Path("benchmarks/scenarios")]
    try:
        loaded = load_scenarios(paths)
    except ScenarioError as exc:
        _fail(str(exc))
        return
    summary = run_scenarios(loaded)
    FlightRecorder().record("arena", {"scenarios": summary.total, "passed": summary.passed})
    if output_json:
        console.print_json(
            json.dumps(
                {
                    "total": summary.total,
                    "passed": summary.passed,
                    "failed": summary.failed,
                    "pass_rate": summary.pass_rate,
                    "results": [
                        r.__dict__
                        | {"expected": r.expected.value, "actual": r.actual.value}
                        for r in summary.results
                    ],
                },
                indent=2,
            )
        )
        return
    table = Table(title="Attack Lab — Scenario Results (simulated, deterministic)")
    table.add_column("Scenario")
    table.add_column("Expected")
    table.add_column("Actual")
    table.add_column("Result")
    for r in summary.results:
        table.add_row(
            r.scenario,
            r.expected.value,
            r.actual.value,
            "[green]PASS[/]" if r.passed else "[red]FAIL[/]",
        )
    console.print(table)
    status = "[green]PASS" if summary.failed == 0 else "[red]FAIL"
    console.print(
        f"Total: {summary.total}  Passed: {summary.passed}  Failed: {summary.failed}  {status}[/]"
    )


@policy_app.command("validate")
def policy_validate(
    path: Path = typer.Argument(  # noqa: B008
        ..., exists=True, readable=True, help="Policy YAML file to validate."
    ),
) -> None:
    """Validate a policy file (structure and rule semantics)."""
    try:
        policy = load_policy(path)
    except PolicyValidationError as exc:
        for problem in exc.errors:
            err_console.print(f"[red]•[/] {problem}")
        _fail(f"policy file '{path}' is invalid")
        return
    console.print(
        f"[green]✔ Policy '{policy.name}' is valid.[/] "
        f"{len(policy.rules)} rules, default: {policy.default.value}."
    )


@policy_app.command("evaluate")
def policy_evaluate(
    path: Path = typer.Argument(  # noqa: B008
        ..., exists=True, readable=True, help="Policy YAML file."
    ),
    action: str = typer.Argument(  # noqa: B008
        ..., help="Action to evaluate (e.g. read, write)."
    ),
    resource: str = typer.Argument(  # noqa: B008
        ..., help="Resource to evaluate (e.g. docs/*)."
    ),
) -> None:
    """Evaluate an action/resource against a policy (deterministic, no LLM)."""
    try:
        policy = load_policy(path)
    except PolicyValidationError as exc:
        _fail(str(exc))
        return
    decision = evaluate(policy, action, resource)
    color = {"allow": "green", "deny": "red", "require_approval": "yellow"}[
        decision.decision.value
    ]
    console.print(f"[bold {color}]{decision.decision.value}[/] — {decision.explanation}")


@mcp_app.command("scan")
def mcp_scan(
    path: Path = typer.Argument(  # noqa: B008
        ..., exists=True, readable=True, help="MCP configuration file."
    ),
    output_json: bool = typer.Option(False, "--json", help="Output results as JSON."),
) -> None:
    """Inspect an MCP configuration file (read-only; never launches servers or tools)."""
    try:
        result = inspect_mcp_config(path)
    except McpInspectError as exc:
        _fail(str(exc))
        return
    FlightRecorder().record("mcp_scan", {"target": str(path), "findings": len(result.findings)})
    if output_json:
        console.print_json(json.dumps(result.model_dump(mode="json")))
    else:
        _print_scan(result)


@app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
) -> None:
    """Start the local AgentFence API (the dashboard connects to it)."""
    import uvicorn
    from agentfence_api.app import create_app

    console.print(BANNER)
    console.print(f"[green]Starting AgentFence API on http://{host}:{port}[/] (Ctrl+C to stop)")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def _print_scan(result: ScanResult) -> None:
    score = score_findings(result.findings)
    console.print(
        Panel(
            f"Target: {result.target}\n"
            f"Files inspected: {result.files_inspected}\n"
            f"Risk score: [bold]{score}/100 ({risk_label(score)})[/]",
            title="Scan complete (read-only)",
        )
    )
    if not result.findings:
        console.print("[green]No findings.[/]")
        return
    table = Table(title="Findings")
    table.add_column("Severity")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("File")
    for f in result.findings:
        color = {
            "critical": "bold red",
            "high": "red",
            "medium": "yellow",
            "low": "cyan",
            "info": "dim",
        }[f.severity.value]
        table.add_row(f"[{color}]{f.severity.value}[/]", f.id, f.title, f.file or "-")
    console.print(table)
    for f in result.findings:
        console.print(f"• [bold]{f.id}[/]: {f.description}")
        console.print(f"  [dim]Remediation:[/] {f.remediation}")
        if f.evidence:
            console.print(f"  [dim]Evidence:[/] `{f.evidence}`")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
