"""Jobs API route handlers for triggering, querying, and approving documentation updates."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from docagent.analyzer.inventory_builder import InventoryBuilder
from docagent.core.logging import logger
from docagent.orchestration.workflow import build_docagent_graph
from docagent.validator.consistency_checker import ConsistencyChecker
from docagent.validator.models import ValidationReport

router = APIRouter(prefix="/jobs", tags=["Jobs"])

# In-memory execution cache for active workflow instances
_ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}
_COMPILED_GRAPH = None


def get_compiled_graph():
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_docagent_graph()
    return _COMPILED_GRAPH


class TriggerJobRequest(BaseModel):
    """Payload to trigger an analysis job."""
    repo_root: str
    trigger_source: str = "api"
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    raw_log_content: Optional[str] = None
    log_file_path: Optional[str] = None
    auto_approve: bool = False


class ApprovalRequest(BaseModel):
    """Payload to approve or reject proposed changes."""
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reviewer_notes: Optional[str] = None


class ValidationRequest(BaseModel):
    """Payload for on-demand validation check."""
    repo_root: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def trigger_analysis_job(req: TriggerJobRequest):
    """Triggers an asynchronous documentation analysis job through the LangGraph engine."""
    repo_path = Path(req.repo_root)
    if not repo_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository path: {req.repo_root}"
        )

    job_id = str(uuid.uuid4())
    initial_state = {
        "job_id": job_id,
        "repo_root": str(repo_path.resolve()),
        "trigger_source": req.trigger_source,
        "base_ref": req.base_ref,
        "head_ref": req.head_ref,
        "raw_log_content": req.raw_log_content,
        "log_file_path": req.log_file_path,
        "auto_approve": req.auto_approve,
    }

    # Execute workflow graph with thread tracking
    config = {"configurable": {"thread_id": job_id}}
    final_state = get_compiled_graph().invoke(initial_state, config=config)

    _ACTIVE_JOBS[job_id] = final_state

    return {
        "job_id": job_id,
        "status": final_state.get("status"),
        "approval_status": final_state.get("approval_status"),
        "proposed_changes_count": len(final_state.get("proposed_changes", [])),
    }


@router.get("/{job_id}")
async def get_job_details(job_id: str):
    """Fetches full state, validation findings, and diffs for a given job ID."""
    state = _ACTIVE_JOBS.get(job_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    return {
        "job_id": job_id,
        "status": state.get("status"),
        "approval_status": state.get("approval_status"),
        "proposed_changes": state.get("proposed_changes", []),
        "validation_report": state.get("validation_report"),
        "execution_history": state.get("execution_history", []),
    }


@router.post("/{job_id}/approve")
async def approve_job_changes(job_id: str, req: ApprovalRequest):
    """Applies or rejects pending documentation changes for a job."""
    state = _ACTIVE_JOBS.get(job_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")

    if state.get("status") != "WAITING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is in state '{state.get('status')}', not WAITING_APPROVAL"
        )

    # Resume graph execution with approval decision
    state["approval_status"] = req.decision
    state["reviewer_notes"] = req.reviewer_notes

    if req.decision == "APPROVED":
        from docagent.orchestration.nodes import node_apply_changes, node_record_execution_history
        apply_res = node_apply_changes(state)
        state.update(apply_res)
        state.update(node_record_execution_history(state))
    else:
        state["status"] = "REJECTED"

    _ACTIVE_JOBS[job_id] = state

    return {
        "job_id": job_id,
        "status": state.get("status"),
        "approval_status": state.get("approval_status"),
    }


@router.post("/validation/check")
async def check_repository_consistency(req: ValidationRequest):
    """Runs on-demand consistency verification without generating changes."""
    repo_path = Path(req.repo_root)
    if not repo_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository directory: {req.repo_root}"
        )

    # Scan and build inventory
    builder = InventoryBuilder(repo_path)
    inventory = builder.build()

    # Validate existing markdown docs
    report = ConsistencyChecker.validate_repository_docs(repo_path, inventory)

    return {
        "repo_name": inventory.repo_name,
        "total_files": inventory.total_files,
        "is_valid": report.is_valid,
        "critical_count": report.critical_count,
        "warning_count": report.warning_count,
        "findings": [f.model_dump() for f in report.findings],
    }
