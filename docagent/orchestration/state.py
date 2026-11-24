"""Typed state definition for LangGraph workflow execution."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class DocAgentState(TypedDict, total=False):
    """Explicit, serializable state passed between LangGraph nodes."""

    # Execution Metadata & Context
    job_id: str
    repo_root: str
    trigger_source: str  # "cli", "vscode", "github_webhook", "scheduled"
    status: str          # "PENDING", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED"
    error_message: Optional[str]

    # Git & Log Inputs
    base_ref: Optional[str]
    head_ref: Optional[str]
    commit_sha: Optional[str]
    log_file_path: Optional[str]
    raw_log_content: Optional[str]

    # Analysis Results
    inventory: Optional[Dict[str, Any]]
    git_changes: Optional[Dict[str, Any]]
    log_results: Optional[Dict[str, Any]]
    existing_docs: Dict[str, str]

    # Generation & Proposals
    impacted_doc_types: List[str]
    proposed_changes: List[Dict[str, Any]]  # Serialized DocProposal list

    # Validation & Safety Bounds
    validation_report: Optional[Dict[str, Any]]
    validation_retry_count: int
    max_validation_retries: int

    # Human-in-the-Loop & Approval
    auto_approve: bool
    approval_status: str  # "PENDING", "APPROVED", "REJECTED"
    reviewer_notes: Optional[str]

    # Execution History / Provenance
    execution_history: List[Dict[str, Any]]
