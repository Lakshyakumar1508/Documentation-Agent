"""Deterministic evidence-anchored documentation templates and section builders."""

from typing import List, Optional, Tuple
from docagent.analyzer.models import CodeInventory, GitChangeSet
from docagent.generator.models import DocProposal, DocType, EvidenceAnchor


def render_readme(
    inventory: CodeInventory,
    summary_text: Optional[str] = None
) -> Tuple[str, List[EvidenceAnchor]]:
    """Builds a comprehensive, grounded README.md."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# {inventory.repo_name}",
        "",
        summary_text or "Production repository analyzed and documented by DocAgent.",
        "",
        "## Table of Contents",
        "- [Architecture Overview](#architecture-overview)",
        "- [Key Modules & Entry Points](#key-modules--entry-points)",
        "- [Installation & Dependencies](#installation--dependencies)",
        "- [API Endpoints](#api-endpoints)",
        "- [Configuration Reference](#configuration-reference)",
        "",
        "## Architecture Overview",
        f"This repository contains **{inventory.total_files}** verified files with primary implementations in Python and JavaScript/TypeScript.",
        "",
        "### Verified Entry Points",
    ]

    for ep in inventory.entry_points:
        lines.append(f"- `{ep}`")
        anchors.append(
            EvidenceAnchor(
                source_file=ep,
                rationale="Detected application entry point"
            )
        )

    lines.extend([
        "",
        "## Key Modules & Entry Points",
        "| Module / File | Language | Exported Symbols |",
        "| :--- | :--- | :--- |",
    ])

    for f in inventory.files[:20]:  # Highlight top 20 files
        symbols_str = ", ".join(f.exported_symbols[:5]) if f.exported_symbols else "-"
        lines.append(f"| `{f.relative_path}` | {f.language.capitalize()} | {symbols_str} |")
        for sym_name in f.exported_symbols[:5]:
            anchors.append(
                EvidenceAnchor(
                    source_file=f.relative_path,
                    symbol_name=sym_name,
                    rationale=f"Exported symbol in {f.relative_path}"
                )
            )

    lines.extend([
        "",
        "## Installation & Dependencies",
        "Dependencies identified from verified package manifests:",
        "",
    ])

    if inventory.dependencies:
        for dep in inventory.dependencies[:15]:
            ver = f" ({dep.version_spec})" if dep.version_spec else ""
            lines.append(f"- **{dep.name}**{ver} [{dep.ecosystem}]")
    else:
        lines.append("No third-party dependencies detected.")

    lines.extend([
        "",
        "## API Endpoints",
    ])

    if inventory.api_routes:
        lines.extend([
            "| HTTP Method | Route Path | Handler Function | Source File |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for r in inventory.api_routes:
            lines.append(f"| `{r.http_method}` | `{r.path}` | `{r.handler_name}` | `{r.file_path}:{r.line_number}` |")
            anchors.append(
                EvidenceAnchor(
                    source_file=r.file_path,
                    symbol_name=r.handler_name,
                    line_start=r.line_number,
                    rationale=f"HTTP endpoint route {r.http_method} {r.path}"
                )
            )
    else:
        lines.append("No HTTP endpoints discovered.")

    lines.extend([
        "",
        "## Configuration Reference",
    ])

    if inventory.configs:
        lines.extend([
            "| Environment / Config Key | Default Value | Secret? | Source File |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for c in inventory.configs:
            secret_flag = "Yes" if c.is_secret else "No"
            default_val = f"`{c.default_value}`" if c.default_value else "-"
            lines.append(f"| `{c.key}` | {default_val} | {secret_flag} | `{c.source_file}` |")
            anchors.append(
                EvidenceAnchor(
                    source_file=c.source_file,
                    symbol_name=c.key,
                    rationale=f"Configuration key detected in {c.source_file}"
                )
            )
    else:
        lines.append("No environment variables or configuration keys detected.")

    lines.append("")
    return "\n".join(lines), anchors


def render_modules_documentation(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates detailed module-by-module documentation."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# Module Reference: {inventory.repo_name}",
        "",
        "This reference documents all internal packages, modules, classes, and exported functions.",
        "",
        "## Discovered Packages & Modules",
        "",
    ]

    # Group files by top-level directory (e.g. src/agents, src/app)
    grouped: dict = {}
    for f in inventory.files:
        if f.language == "python" and not f.relative_path.startswith("tests"):
            parts = f.relative_path.replace("\\", "/").split("/")
            group_name = "/".join(parts[:2]) if len(parts) > 1 else "root"
            grouped.setdefault(group_name, []).append(f)

    for group, files in sorted(grouped.items()):
        lines.extend([
            f"### Package `{group}`",
            "",
            "| Module | Exported Symbols | Line Count |",
            "| :--- | :--- | :--- |",
        ])
        for f in sorted(files, key=lambda x: x.relative_path):
            symbols_in_file = [s for s in inventory.symbols if s.file_path == f.relative_path and s.is_exported]
            sym_names = [s.name for s in symbols_in_file]
            sym_str = ", ".join(sym_names[:6]) if sym_names else "*No public exports*"
            lines.append(f"| `{f.relative_path}` | {sym_str} | {f.size_bytes}B |")

            for s in symbols_in_file:
                anchors.append(
                    EvidenceAnchor(
                        source_file=f.relative_path,
                        symbol_name=s.qualified_name,
                        line_start=s.start_line,
                        line_end=s.end_line,
                        rationale=f"Documented {s.kind.value} {s.qualified_name}"
                    )
                )
        lines.append("")

    return "\n".join(lines), anchors


def render_onboarding_guide(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates developer onboarding and local setup guide."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# Developer Onboarding & Setup Guide: {inventory.repo_name}",
        "",
        "Welcome to the project! This guide walks through setting up your local development environment.",
        "",
        "## 1. Prerequisites",
        "- Python 3.10+",
        "- Git",
    ]

    # Check for docker
    if any("docker" in c.key.lower() for c in inventory.configs):
        lines.append("- Docker (optional, required if Docker code sandbox is enabled)")

    lines.extend([
        "",
        "## 2. Environment Setup",
        "```bash",
        "# Clone the repository",
        f"git clone <repo-url>",
        f"cd {inventory.repo_name}",
        "",
        "# Create and activate virtual environment",
        "python -m venv .venv",
        "source .venv/bin/activate  # On Windows: .venv\\Scripts\\Activate.ps1",
        "",
        "# Install dependencies",
        "pip install -r requirements.txt",
        "```",
        "",
        "## 3. Configuration Reference",
        "Copy `.env.example` to `.env` and set the following required keys:",
        "",
        "| Variable | Required? | Default | Description |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for c in inventory.configs:
        is_req = "Yes" if c.is_secret or not c.default_value else "Optional"
        lines.append(f"| `{c.key}` | {is_req} | `{c.default_value or '-'}` | `{c.source_file}` |")
        anchors.append(EvidenceAnchor(source_file=c.source_file, symbol_name=c.key))

    lines.extend([
        "",
        "## 4. Running the Application",
    ])

    for ep in inventory.entry_points:
        lines.append(f"- Run entrypoint: `python {ep}`")

    lines.extend([
        "",
        "## 5. Running Tests",
        "```bash",
        "pytest tests/ -v",
        "```",
        "",
    ])

    return "\n".join(lines), anchors


def render_api_reference(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates detailed API reference documentation."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        "# API Reference Documentation",
        "",
        "This document details verified HTTP endpoints and public API interfaces.",
        "",
    ]

    if not inventory.api_routes:
        lines.append("No HTTP API routes detected in the repository.\n")
        return "\n".join(lines), anchors

    for r in inventory.api_routes:
        lines.extend([
            f"### `{r.http_method} {r.path}`",
            "",
            f"- **Handler**: `{r.handler_name}`",
            f"- **Source**: `{r.file_path}#L{r.line_number}`",
            f"- **Authentication**: {'Required' if r.auth_required else 'None / Optional'}",
            "",
        ])
        anchors.append(
            EvidenceAnchor(
                source_file=r.file_path,
                symbol_name=r.handler_name,
                line_start=r.line_number,
                rationale=f"Endpoint {r.http_method} {r.path}"
            )
        )

    return "\n".join(lines), anchors


def render_configuration_reference(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates configuration and environment variable reference."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        "# Configuration & Environment Variable Reference",
        "",
        "All environment variables discovered through static code inspection.",
        "",
        "| Key | Default | Sensitive | Declared In |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for c in inventory.configs:
        sec = "Yes" if c.is_secret else "No"
        def_str = f"`{c.default_value}`" if c.default_value else "*None*"
        lines.append(f"| `{c.key}` | {def_str} | {sec} | `{c.source_file}` |")
        anchors.append(
            EvidenceAnchor(
                source_file=c.source_file,
                symbol_name=c.key,
                rationale="Configuration variable"
            )
        )

    lines.append("")
    return "\n".join(lines), anchors


def render_modules_documentation(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates detailed module-by-module documentation."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# Module Reference: {inventory.repo_name}",
        "",
        "This reference documents all internal packages, modules, classes, and exported functions.",
        "",
        "## Discovered Packages & Modules",
        "",
    ]

    # Group files by top-level directory (e.g. src/agents, src/app)
    grouped: dict = {}
    for f in inventory.files:
        if f.language == "python" and not f.relative_path.startswith("tests"):
            parts = f.relative_path.replace("\\", "/").split("/")
            group_name = "/".join(parts[:2]) if len(parts) > 1 else "root"
            grouped.setdefault(group_name, []).append(f)

    for group, files in sorted(grouped.items()):
        lines.extend([
            f"### Package `{group}`",
            "",
            "| Module | Exported Symbols | Line Count |",
            "| :--- | :--- | :--- |",
        ])
        for f in sorted(files, key=lambda x: x.relative_path):
            symbols_in_file = [s for s in inventory.symbols if s.file_path == f.relative_path and s.is_exported]
            sym_names = [s.name for s in symbols_in_file]
            sym_str = ", ".join(sym_names[:6]) if sym_names else "*No public exports*"
            lines.append(f"| `{f.relative_path}` | {sym_str} | {f.size_bytes}B |")

            for s in symbols_in_file:
                anchors.append(
                    EvidenceAnchor(
                        source_file=f.relative_path,
                        symbol_name=s.qualified_name,
                        line_start=s.start_line,
                        line_end=s.end_line,
                        rationale=f"Documented {s.kind.value} {s.qualified_name}"
                    )
                )
        lines.append("")

    return "\n".join(lines), anchors


def render_onboarding_guide(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates developer onboarding and local setup guide."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# Developer Onboarding & Setup Guide: {inventory.repo_name}",
        "",
        "Welcome to the project! This guide walks through setting up your local development environment.",
        "",
        "## 1. Prerequisites",
        "- Python 3.10+",
        "- Git",
    ]

    # Check for docker
    if any("docker" in c.key.lower() for c in inventory.configs):
        lines.append("- Docker (optional, required if Docker code sandbox is enabled)")

    lines.extend([
        "",
        "## 2. Environment Setup",
        "```bash",
        "# Clone the repository",
        f"git clone <repo-url>",
        f"cd {inventory.repo_name}",
        "",
        "# Create and activate virtual environment",
        "python -m venv .venv",
        "source .venv/bin/activate  # On Windows: .venv\\Scripts\\Activate.ps1",
        "",
        "# Install dependencies",
        "pip install -r requirements.txt",
        "```",
        "",
        "## 3. Configuration Reference",
        "Copy `.env.example` to `.env` and set the following required keys:",
        "",
        "| Variable | Required? | Default | Description |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for c in inventory.configs:
        is_req = "Yes" if c.is_secret or not c.default_value else "Optional"
        lines.append(f"| `{c.key}` | {is_req} | `{c.default_value or '-'}` | `{c.source_file}` |")
        anchors.append(EvidenceAnchor(source_file=c.source_file, symbol_name=c.key))

    lines.extend([
        "",
        "## 4. Running the Application",
    ])

    for ep in inventory.entry_points:
        lines.append(f"- Run entrypoint: `python {ep}`")

    lines.extend([
        "",
        "## 5. Running Tests",
        "```bash",
        "pytest tests/ -v",
        "```",
        "",
    ])

    return "\n".join(lines), anchors


def render_changelog(change_set: GitChangeSet) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates semantic changelog from Git changes and breaking change detections."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        "# Changelog",
        "",
        f"## Changes (Base: `{change_set.base_ref or 'HEAD'}`, Head: `{change_set.head_ref or 'HEAD'}`)",
        "",
    ]

    if change_set.breaking_changes:
        lines.extend([
            "### ⚠️ Breaking Changes",
            "",
        ])
        for b in change_set.breaking_changes:
            lines.append(f"- **[{b.severity.upper()}]** `{b.symbol_name}`: {b.description} (`{b.file_path}`)")
            anchors.append(
                EvidenceAnchor(
                    source_file=b.file_path,
                    symbol_name=b.symbol_name,
                    rationale=b.description
                )
            )
        lines.append("")

    lines.extend([
        "### Modified Files",
        "",
    ])

    for f in change_set.files_changed:
        lines.append(f"- **{f.change_type.value.upper()}**: `{f.file_path}`")
        anchors.append(
            EvidenceAnchor(
                source_file=f.file_path,
                rationale=f"File {f.change_type.value}"
            )
        )

    if change_set.affected_symbol_names:
        lines.extend([
            "",
            "### Affected Code Symbols",
            "",
        ])
        for sym in change_set.affected_symbol_names:
            lines.append(f"- `{sym}`")

    lines.append("")
    return "\n".join(lines), anchors


def render_modules_documentation(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates detailed module-by-module documentation."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# Module Reference: {inventory.repo_name}",
        "",
        "This reference documents all internal packages, modules, classes, and exported functions.",
        "",
        "## Discovered Packages & Modules",
        "",
    ]

    # Group files by top-level directory (e.g. src/agents, src/app)
    grouped: dict = {}
    for f in inventory.files:
        if f.language == "python" and not f.relative_path.startswith("tests"):
            parts = f.relative_path.replace("\\", "/").split("/")
            group_name = "/".join(parts[:2]) if len(parts) > 1 else "root"
            grouped.setdefault(group_name, []).append(f)

    for group, files in sorted(grouped.items()):
        lines.extend([
            f"### Package `{group}`",
            "",
            "| Module | Exported Symbols | Line Count |",
            "| :--- | :--- | :--- |",
        ])
        for f in sorted(files, key=lambda x: x.relative_path):
            symbols_in_file = [s for s in inventory.symbols if s.file_path == f.relative_path and s.is_exported]
            sym_names = [s.name for s in symbols_in_file]
            sym_str = ", ".join(sym_names[:6]) if sym_names else "*No public exports*"
            lines.append(f"| `{f.relative_path}` | {sym_str} | {f.size_bytes}B |")

            for s in symbols_in_file:
                anchors.append(
                    EvidenceAnchor(
                        source_file=f.relative_path,
                        symbol_name=s.qualified_name,
                        line_start=s.start_line,
                        line_end=s.end_line,
                        rationale=f"Documented {s.kind.value} {s.qualified_name}"
                    )
                )
        lines.append("")

    return "\n".join(lines), anchors


def render_onboarding_guide(inventory: CodeInventory) -> Tuple[str, List[EvidenceAnchor]]:
    """Generates developer onboarding and local setup guide."""
    anchors: List[EvidenceAnchor] = []
    lines: List[str] = [
        f"# Developer Onboarding & Setup Guide: {inventory.repo_name}",
        "",
        "Welcome to the project! This guide walks through setting up your local development environment.",
        "",
        "## 1. Prerequisites",
        "- Python 3.10+",
        "- Git",
    ]

    # Check for docker
    if any("docker" in c.key.lower() for c in inventory.configs):
        lines.append("- Docker (optional, required if Docker code sandbox is enabled)")

    lines.extend([
        "",
        "## 2. Environment Setup",
        "```bash",
        "# Clone the repository",
        f"git clone <repo-url>",
        f"cd {inventory.repo_name}",
        "",
        "# Create and activate virtual environment",
        "python -m venv .venv",
        "source .venv/bin/activate  # On Windows: .venv\\Scripts\\Activate.ps1",
        "",
        "# Install dependencies",
        "pip install -r requirements.txt",
        "```",
        "",
        "## 3. Configuration Reference",
        "Copy `.env.example` to `.env` and set the following required keys:",
        "",
        "| Variable | Required? | Default | Description |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for c in inventory.configs:
        is_req = "Yes" if c.is_secret or not c.default_value else "Optional"
        lines.append(f"| `{c.key}` | {is_req} | `{c.default_value or '-'}` | `{c.source_file}` |")
        anchors.append(EvidenceAnchor(source_file=c.source_file, symbol_name=c.key))

    lines.extend([
        "",
        "## 4. Running the Application",
    ])

    for ep in inventory.entry_points:
        lines.append(f"- Run entrypoint: `python {ep}`")

    lines.extend([
        "",
        "## 5. Running Tests",
        "```bash",
        "pytest tests/ -v",
        "```",
        "",
    ])

    return "\n".join(lines), anchors
