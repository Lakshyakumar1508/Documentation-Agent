"""LangGraph controlled workflow graph assembling all nodes and conditional edges."""

from typing import Any, Dict, Literal, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from docagent.orchestration.nodes import (
    node_apply_changes,
    node_check_unsupported_claims,
    node_collect_git_changes,
    node_collect_relevant_logs,
    node_generate_proposed_changes,
    node_identify_doc_impact,
    node_identify_repository,
    node_record_execution_history,
    node_retrieve_existing_docs,
    node_scan_and_build_inventory,
    node_validate_proposed_changes,
    node_validate_request,
)
from docagent.orchestration.state import DocAgentState


def route_after_request_validation(state: DocAgentState) -> Literal["identify_repository", "record_execution_history"]:
    """Early exit if request validation fails."""
    if state.get("status") == "FAILED":
        return "record_execution_history"
    return "identify_repository"


def route_after_unsupported_claims_check(
    state: DocAgentState
) -> Literal["generate_proposed_changes", "apply_changes", "record_execution_history"]:
    """Evaluates retry loop or advances to apply / review."""
    report_dict = state.get("validation_report", {})
    is_valid = report_dict.get("is_valid", True)
    retries = state.get("validation_retry_count", 0)
    max_retries = state.get("max_validation_retries", 2)

    # If critical validation errors occur and retries remain, loop back
    if not is_valid and retries < max_retries:
        return "generate_proposed_changes"

    # If changes are approved (auto_approve or approved via human review), apply them
    if state.get("approval_status") == "APPROVED":
        return "apply_changes"

    # Otherwise finalize execution history (e.g. WAITING_APPROVAL or REJECTED)
    return "record_execution_history"


def build_docagent_graph(checkpointer: Optional[Any] = None) -> Any:
    """
    Constructs and compiles the bounded LangGraph DAG for the Documentation Agent.
    
    START
      -> Validate Request
      -> Identify Repository
      -> Scan & Build Inventory
      -> Collect Git Changes
      -> Collect Relevant Logs
      -> Retrieve Existing Docs
      -> Identify Doc Impact
      -> Generate Proposed Changes
      -> Validate Against Source Code
      -> Check For Unsupported Claims
      -> [Conditional Retry or Apply]
      -> Record Execution History
      -> END
    """
    builder = StateGraph(DocAgentState)

    # Register Nodes
    builder.add_node("validate_request", node_validate_request)
    builder.add_node("identify_repository", node_identify_repository)
    builder.add_node("scan_and_build_inventory", node_scan_and_build_inventory)
    builder.add_node("collect_git_changes", node_collect_git_changes)
    builder.add_node("collect_relevant_logs", node_collect_relevant_logs)
    builder.add_node("retrieve_existing_docs", node_retrieve_existing_docs)
    builder.add_node("identify_doc_impact", node_identify_doc_impact)
    builder.add_node("generate_proposed_changes", node_generate_proposed_changes)
    builder.add_node("validate_against_source_code", node_validate_proposed_changes)
    builder.add_node("check_for_unsupported_claims", node_check_unsupported_claims)
    builder.add_node("apply_changes", node_apply_changes)
    builder.add_node("record_execution_history", node_record_execution_history)

    # Edge Definitions
    builder.add_edge(START, "validate_request")
    builder.add_conditional_edges(
        "validate_request",
        route_after_request_validation,
        {
            "identify_repository": "identify_repository",
            "record_execution_history": "record_execution_history",
        }
    )
    builder.add_edge("identify_repository", "scan_and_build_inventory")
    builder.add_edge("scan_and_build_inventory", "collect_git_changes")
    builder.add_edge("collect_git_changes", "collect_relevant_logs")
    builder.add_edge("collect_relevant_logs", "retrieve_existing_docs")
    builder.add_edge("retrieve_existing_docs", "identify_doc_impact")
    builder.add_edge("identify_doc_impact", "generate_proposed_changes")
    builder.add_edge("generate_proposed_changes", "validate_against_source_code")
    builder.add_edge("validate_against_source_code", "check_for_unsupported_claims")

    builder.add_conditional_edges(
        "check_for_unsupported_claims",
        route_after_unsupported_claims_check,
        {
            "generate_proposed_changes": "generate_proposed_changes",
            "apply_changes": "apply_changes",
            "record_execution_history": "record_execution_history",
        }
    )

    builder.add_edge("apply_changes", "record_execution_history")
    builder.add_edge("record_execution_history", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)
