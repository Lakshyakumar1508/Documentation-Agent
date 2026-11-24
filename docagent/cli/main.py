"""Production Typer CLI interface for DocAgent with Rich visual formatting."""

import os
from pathlib import Path
import sys
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import typer

from docagent.analyzer.inventory_builder import InventoryBuilder
from docagent.analyzer.log_analyzer import LogAnalyzer
from docagent.core.logging import logger
from docagent.orchestration.workflow import build_docagent_graph
from docagent.validator.consistency_checker import ConsistencyChecker
from docagent.validator.models import FindingSeverity

app = typer.Typer(
    name="docagent",
    help="Intelligent Documentation Agent CLI: Analyze, Generate, Validate, and Monitor Documentation.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Target repository directory."),
):
    """Initializes DocAgent configuration and .docagentignore in the workspace."""
    repo_root = path.resolve()
    if not repo_root.is_dir():
        console.print(f"[bold red]Error:[/bold red] Directory '{repo_root}' does not exist.")
        raise typer.Exit(code=1)

    ignore_file = repo_root / ".docagentignore"
    if ignore_file.exists():
        console.print(f"[yellow].docagentignore already exists at {ignore_file}[/yellow]")
    else:
        default_ignore = (
            "# DocAgent Ignore Patterns\n"
            ".venv/\n"
            "node_modules/\n"
            "__pycache__/\n"
            "*.pyc\n"
            "dist/\n"
            "build/\n"
            "coverage/\n"
            ".git/\n"
            ".env*\n"
        )
        ignore_file.write_text(default_ignore, encoding="utf-8")
        console.print(f"[bold green]Created .docagentignore at {ignore_file}[/bold green]")

    # Create docs directory if not present
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(exist_ok=True)
    console.print(f"[bold green]Ensured docs/ directory exists at {docs_dir}[/bold green]")
    console.print(Panel.fit("[bold cyan]DocAgent successfully initialized![/bold cyan]\nRun `docagent analyze` next."))


@app.command()
def analyze(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Target repository directory."),
):
    """Scans repository structure, extracting symbols, API routes, and configuration."""
    repo_root = path.resolve()
    with console.status("[bold green]Analyzing repository structure and parsing code AST...[/bold green]"):
        builder = InventoryBuilder(repo_root)
        inventory = builder.build()

    console.print(Panel(f"[bold]Repository Analysis:[/] [cyan]{inventory.repo_name}[/]\nFiles: {inventory.total_files} | Symbols: {len(inventory.symbols)} | Routes: {len(inventory.api_routes)} | Configs: {len(inventory.configs)}"))

    # Display API Routes Table
    if inventory.api_routes:
        table = Table(title="Discovered API Routes", show_header=True, header_style="bold magenta")
        table.add_column("Method", style="cyan", width=8)
        table.add_column("Path", style="green")
        table.add_column("Handler", style="white")
        table.add_column("Source", style="dim")
        for r in inventory.api_routes:
            table.add_row(r.http_method, r.path, r.handler_name, f"{r.file_path}:{r.line_number}")
        console.print(table)

    # Display Configs Table
    if inventory.configs:
        cfg_table = Table(title="Configuration & Environment Variables", show_header=True, header_style="bold blue")
        cfg_table.add_column("Key", style="bold")
        cfg_table.add_column("Default", style="dim")
        cfg_table.add_column("Sensitive", style="red")
        cfg_table.add_column("Source", style="cyan")
        for c in inventory.configs:
            cfg_table.add_row(c.key, c.default_value or "-", "Yes" if c.is_secret else "No", c.source_file)
        console.print(cfg_table)


@app.command()
def generate(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Target repository directory."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve and apply proposed changes without prompt."),
):
    """Runs LangGraph documentation generator and displays unified diff review."""
    repo_root = path.resolve()
    console.print(f"[bold cyan]Starting DocAgent generation workflow for: {repo_root}[/bold cyan]")

    graph = build_docagent_graph()
    initial_state = {
        "job_id": f"cli-{int(time.time())}",
        "repo_root": str(repo_root),
        "trigger_source": "cli",
        "auto_approve": yes,
    }

    config = {"configurable": {"thread_id": initial_state["job_id"]}}
    state = graph.invoke(initial_state, config=config)

    proposals = state.get("proposed_changes", [])
    if not proposals:
        console.print("[yellow]No documentation changes proposed.[/yellow]")
        return

    console.print(f"\n[bold green]Generated {len(proposals)} documentation proposal(s):[/bold green]")

    for p in proposals:
        file_path = p.get("file_path", "")
        diff = p.get("unified_diff", "")
        rationale = p.get("rationale", "")

        console.print(Panel(f"[bold]{file_path}[/bold]\nRationale: {rationale}", title="Proposed Change"))
        if diff.strip():
            syntax = Syntax(diff, "diff", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            console.print("[dim]New file content generated.[/dim]")

    if not yes:
        confirm = typer.confirm("Apply these documentation changes to disk?", default=False)
        if confirm:
            from docagent.orchestration.nodes import node_apply_changes
            state["approval_status"] = "APPROVED"
            node_apply_changes(state)
            console.print("[bold green]Documentation changes successfully applied![/bold green]")
        else:
            console.print("[yellow]Changes were discarded.[/yellow]")
    else:
        console.print("[bold green]Changes automatically applied (--yes).[/bold green]")


@app.command()
def validate(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Target repository directory."),
):
    """Compares existing documentation against source code to detect drift and hallucinations."""
    repo_root = path.resolve()
    with console.status("[bold green]Verifying documentation consistency against codebase...[/bold green]"):
        builder = InventoryBuilder(repo_root)
        inventory = builder.build()
        report = ConsistencyChecker.validate_repository_docs(repo_root, inventory)

    if report.is_valid and report.warning_count == 0:
        console.print(Panel.fit("[bold green]✓ All documentation claims are verified and grounded in source code.[/bold green]"))
        return

    table = Table(title="Documentation Drift & Consistency Report", show_header=True, header_style="bold red")
    table.add_column("Severity", width=10)
    table.add_column("Rule", width=22)
    table.add_column("Document", style="cyan")
    table.add_column("Claim / Issue", style="white")
    table.add_column("Fix Recommendation", style="green")

    for f in report.findings:
        sev_style = "bold red" if f.severity == FindingSeverity.CRITICAL else "bold yellow"
        table.add_row(
            f"[{sev_style}]{f.severity.upper()}[/{sev_style}]",
            f.rule.value,
            f"{f.doc_file}:{f.line_number or 0}",
            f.message,
            f.suggested_fix or "-",
        )

    console.print(table)
    console.print(f"\nTotal Issues: [red]{report.critical_count} Critical[/red], [yellow]{report.warning_count} Warnings[/yellow]")
    if report.critical_count > 0:
        raise typer.Exit(code=1)


@app.command()
def logs(
    file: Path = typer.Argument(..., help="Path to log file (application or CI trace)."),
):
    """Parses application or CI logs, grouping repetitive errors and clustering failures."""
    log_file = file.resolve()
    if not log_file.is_file():
        console.print(f"[bold red]Error:[/bold red] Log file not found: {log_file}")
        raise typer.Exit(code=1)

    analyzer = LogAnalyzer()
    res = analyzer.analyze_file(log_file)

    console.print(Panel(f"[bold]Log Analysis Summary for:[/] [cyan]{log_file.name}[/]\nEntries: {res.total_entries} | Errors: {res.error_count} | Warnings: {res.warning_count} | Clusters: {len(res.clusters)}"))

    if res.clusters:
        table = Table(title="Error Clusters (Fingerprinted Signatures)", show_header=True, header_style="bold magenta")
        table.add_column("Signature", width=12, style="cyan")
        table.add_column("Error Type", style="bold red")
        table.add_column("Count", width=8, justify="right")
        table.add_column("Message Preview", style="white")
        table.add_column("Files", style="dim")

        for c in res.clusters:
            table.add_row(
                c.signature_hash,
                c.error_type,
                str(c.occurrences),
                c.representative_message[:60],
                ", ".join(c.affected_files[:2]) or "-",
            )
        console.print(table)

    if res.inferred_recommendations:
        console.print("\n[bold green]Operational Recommendations:[/bold green]")
        for r in res.inferred_recommendations:
            console.print(f"- {r}")


@app.command()
def watch(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Target repository directory."),
    interval: int = typer.Option(3, "--interval", "-i", help="Polling interval in seconds."),
):
    """Monitors local repository changes and alerts on documentation drift."""
    repo_root = path.resolve()
    console.print(f"[bold cyan]Watching {repo_root} for code changes (interval: {interval}s)... Press Ctrl+C to stop.[/bold cyan]")

    builder = InventoryBuilder(repo_root)
    last_inv = builder.build()
    last_hashes = {f.relative_path: f.sha256_hash for f in last_inv.files}

    try:
        while True:
            time.sleep(interval)
            current_inv = builder.build()
            current_hashes = {f.relative_path: f.sha256_hash for f in current_inv.files}

            changed_files = [
                path for path, h in current_hashes.items()
                if path not in last_hashes or last_hashes[path] != h
            ]

            if changed_files:
                console.print(f"\n[bold yellow][{time.strftime('%H:%M:%S')}] Detected changes in {len(changed_files)} file(s):[/bold yellow]")
                for cf in changed_files:
                    console.print(f"  • {cf}")

                # Run consistency check
                report = ConsistencyChecker.validate_repository_docs(repo_root, current_inv)
                if not report.is_valid:
                    console.print(f"[bold red]⚠️ Documentation drift detected! {report.critical_count} critical issue(s).[/bold red]")
                else:
                    console.print("[green]Documentation remains consistent with codebase.[/green]")

                last_hashes = current_hashes
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch stopped by user.[/yellow]")


def main():
    """Main CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()

