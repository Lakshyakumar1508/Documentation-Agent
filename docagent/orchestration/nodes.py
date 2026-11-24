"""Node implementations for the LangGraph documentation workflow."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from docagent.analyzer.git_diff_analyzer import GitDiffAnalyzer
from docagent.analyzer.inventory_builder import InventoryBuilder
from docagent.analyzer.log_analyzer import LogAnalyzer
from docagent.analyzer.models import CodeInventory, GitChangeSet, LogAnalysisResult
from docagent.core.logging import logger
from docagent.generator.doc_generator import DocGenerator
from docagent.generator.models import DocProposal, DocType
from docagent.orchestration.state import DocAgentState
from docagent.security.path_validator import validate_contained_path
from docagent.validator.consistency_checker import ConsistencyChecker
from docagent.validator.models import ValidationReport


def node_validate_request(state: DocAgentState) -> Dict[str, Any]:
    """Validates incoming request payload, directory existence, and initializes job ID."""
    repo_path = state.get("repo_root", "")
    job_id = state.get("job_id") or str(uuid.uuid4())
    logger.info(f"[{job_id}] Validating request for repo: {repo_path}")

    step_record = {
        "node": "validate_request",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "SUCCESS",
    }

    if not repo_path or not Path(repo_path).is_dir():
        return {
            "job_id": job_id,
            "status": "FAILED",
            "error_message": f"Repository directory does not exist or is invalid: {repo_path}",
            "execution_history": state.get("execution_history", []) + [step_record],
        }

    return {
        "job_id": job_id,
        "status": "RUNNING",
        "validation_retry_count": state.get("validation_retry_count", 0),
        "max_validation_retries": state.get("max_validation_retries", 2),
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_identify_repository(state: DocAgentState) -> Dict[str, Any]:
    """Inspects Git repository parameters and active branches."""
    repo_root = Path(state["repo_root"])
    analyzer = GitDiffAnalyzer(repo_root)
    is_git = analyzer.is_git_repo()

    step_record = {
        "node": "identify_repository",
        "is_git": is_git,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "execution_history": state.get("execution_history", []) + [step_record]
    }


def node_scan_and_build_inventory(state: DocAgentState) -> Dict[str, Any]:
    """Scans filesystem and builds complete AST / Tree-sitter CodeInventory."""
    repo_root = Path(state["repo_root"])
    logger.info(f"[{state['job_id']}] Building code inventory for {repo_root}")

    builder = InventoryBuilder(repo_root)
    inventory = builder.build()

    step_record = {
        "node": "build_code_inventory",
        "files_indexed": inventory.total_files,
        "symbols_indexed": len(inventory.symbols),
        "routes_indexed": len(inventory.api_routes),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "inventory": inventory.model_dump(),
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_collect_git_changes(state: DocAgentState) -> Dict[str, Any]:
    """Inspects Git working tree or commit range for diffs and breaking changes."""
    repo_root = Path(state["repo_root"])
    analyzer = GitDiffAnalyzer(repo_root)

    current_inv = CodeInventory(**state["inventory"]) if state.get("inventory") else None

    base_ref = state.get("base_ref")
    head_ref = state.get("head_ref")

    if base_ref and head_ref:
        change_set = analyzer.get_commit_range_changes(
            base_ref=base_ref,
            head_ref=head_ref,
            new_inventory=current_inv
        )
    else:
        change_set = analyzer.get_working_tree_changes(current_inventory=current_inv)

    step_record = {
        "node": "collect_git_changes",
        "files_changed": len(change_set.files_changed),
        "breaking_changes": len(change_set.breaking_changes),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "git_changes": change_set.model_dump(),
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_collect_relevant_logs(state: DocAgentState) -> Dict[str, Any]:
    """Parses application or CI logs and clusters errors."""
    repo_root = Path(state["repo_root"])
    analyzer = LogAnalyzer(repo_root)
    log_result = LogAnalysisResult()

    raw_text = state.get("raw_log_content")
    log_path = state.get("log_file_path")

    if raw_text:
        log_result = analyzer.analyze_log_content(raw_text)
    elif log_path:
        full_log_path = Path(log_path)
        if not full_log_path.is_absolute():
            full_log_path = repo_root / log_path
        if full_log_path.is_file():
            log_result = analyzer.analyze_file(full_log_path)

    step_record = {
        "node": "collect_relevant_logs",
        "errors_parsed": log_result.error_count,
        "clusters_formed": len(log_result.clusters),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "log_results": log_result.model_dump(),
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_retrieve_existing_docs(state: DocAgentState) -> Dict[str, Any]:
    """Reads existing documentation files in the workspace."""
    repo_root = Path(state["repo_root"])
    doc_paths = [
        "README.md",
        "docs/api_reference.md",
        "docs/configuration.md",
        "CHANGELOG.md",
        "docs/troubleshooting.md",
    ]

    existing: Dict[str, str] = {}
    for rel_path in doc_paths:
        full_p = repo_root / rel_path
        if full_p.is_file():
            try:
                existing[rel_path] = full_p.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Failed to read existing doc {rel_path}: {e}")

    step_record = {
        "node": "retrieve_existing_docs",
        "docs_retrieved": list(existing.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "existing_docs": existing,
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_identify_doc_impact(state: DocAgentState) -> Dict[str, Any]:
    """Determines which documentation files need to be generated or refreshed."""
    impacted: List[str] = ["configuration", "modules", "onboarding"]

    inv_data = state.get("inventory")
    if inv_data and inv_data.get("api_routes"):
        impacted.append("api_reference")

    # If README doesn't exist or is requested, include it
    existing_docs = state.get("existing_docs", {})
    if "README.md" not in existing_docs:
        impacted.append("readme")

    git_changes = GitChangeSet(**state["git_changes"]) if state.get("git_changes") else None
    if git_changes and (git_changes.files_changed or git_changes.breaking_changes):
        impacted.append("changelog")

    log_results = LogAnalysisResult(**state["log_results"]) if state.get("log_results") else None
    if log_results and log_results.error_count > 0:
        impacted.append("troubleshooting")

    step_record = {
        "node": "identify_doc_impact",
        "impacted": impacted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "impacted_doc_types": impacted,
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_generate_proposed_changes(state: DocAgentState) -> Dict[str, Any]:
    """Generates DocProposal objects grounded in AST and Git evidence."""
    repo_root = Path(state["repo_root"])
    generator = DocGenerator(repo_root)

    inv = CodeInventory(**state["inventory"])
    git_changes = GitChangeSet(**state["git_changes"]) if state.get("git_changes") else None
    log_results = LogAnalysisResult(**state["log_results"]) if state.get("log_results") else None

    impacted = state.get("impacted_doc_types", [])
    proposals: List[DocProposal] = []

    if "readme" in impacted:
        proposals.append(generator.generate_readme(inv))
    if "api_reference" in impacted and inv.api_routes:
        proposals.append(generator.generate_api_reference(inv))
    if "configuration" in impacted:
        proposals.append(generator.generate_configuration_reference(inv))
    if "modules" in impacted:
        proposals.append(generator.generate_modules_reference(inv))
    if "onboarding" in impacted:
        proposals.append(generator.generate_onboarding_guide(inv))
    if "changelog" in impacted and git_changes:
        proposals.append(generator.generate_changelog(git_changes))
    if "troubleshooting" in impacted and log_results:
        log_analyzer = LogAnalyzer(repo_root)
        proposals.append(log_analyzer.render_troubleshooting_guide(log_results))

    step_record = {
        "node": "generate_proposed_changes",
        "proposals_generated": [p.file_path for p in proposals],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "proposed_changes": [p.model_dump() for p in proposals],
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_validate_proposed_changes(state: DocAgentState) -> Dict[str, Any]:
    """Validates proposed documentation changes against source code inventory."""
    inv = CodeInventory(**state["inventory"])
    proposals = [DocProposal(**p) for p in state.get("proposed_changes", [])]

    aggregated_report = ValidationReport()

    for p in proposals:
        doc_report = ConsistencyChecker.validate_document(
            doc_path=p.file_path,
            doc_content=p.proposed_content,
            inventory=inv,
        )
        for finding in doc_report.findings:
            aggregated_report.add_finding(finding)

    step_record = {
        "node": "validate_against_source_code",
        "is_valid": aggregated_report.is_valid,
        "critical_findings": aggregated_report.critical_count,
        "warning_findings": aggregated_report.warning_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "validation_report": aggregated_report.model_dump(),
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_check_unsupported_claims(state: DocAgentState) -> Dict[str, Any]:
    """Evaluates validation results to decide on human approval or bounded retry."""
    report_dict = state.get("validation_report", {})
    report = ValidationReport(**report_dict) if report_dict else ValidationReport()

    current_retries = state.get("validation_retry_count", 0)
    max_retries = state.get("max_validation_retries", 2)

    needs_retry = (not report.is_valid) and (current_retries < max_retries)

    if needs_retry:
        logger.warning(
            f"Validation encountered {report.critical_count} critical issues. "
            f"Retrying generation (Attempt {current_retries + 1}/{max_retries})"
        )
        return {
            "validation_retry_count": current_retries + 1,
            "status": "RUNNING",
        }

    # Ready for human review
    auto = state.get("auto_approve", False)
    status = "APPROVED" if auto else "WAITING_APPROVAL"

    step_record = {
        "node": "check_for_unsupported_claims",
        "ready_for_approval": True,
        "auto_approve": auto,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "approval_status": status,
        "status": status,
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_apply_changes(state: DocAgentState) -> Dict[str, Any]:
    """Applies approved documentation changes to files on disk."""
    if state.get("approval_status") != "APPROVED":
        logger.info("Changes not approved. Skipping apply_changes.")
        return {}

    repo_root = Path(state["repo_root"])
    proposals = [DocProposal(**p) for p in state.get("proposed_changes", [])]
    applied_files: List[str] = []

    for p in proposals:
        target_path = validate_contained_path(repo_root, repo_root / p.file_path, allow_nonexistent=True)
        # Ensure parent directories exist
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(p.proposed_content, encoding="utf-8")
        applied_files.append(p.file_path)
        logger.info(f"Applied documentation change to {target_path}")

    step_record = {
        "node": "apply_changes",
        "applied_files": applied_files,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": "COMPLETED",
        "execution_history": state.get("execution_history", []) + [step_record],
    }


def node_record_execution_history(state: DocAgentState) -> Dict[str, Any]:
    """Finalizes execution trace and returns summary."""
    final_status = state.get("status", "COMPLETED")
    if state.get("approval_status") == "REJECTED":
        final_status = "REJECTED"

    step_record = {
        "node": "record_execution_history",
        "final_status": final_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": final_status,
        "execution_history": state.get("execution_history", []) + [step_record],
    }
