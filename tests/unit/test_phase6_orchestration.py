"""Unit tests for Phase 6: LangGraph Controlled Orchestration Workflow."""

from pathlib import Path
import pytest

from docagent.orchestration.workflow import build_docagent_graph


def test_workflow_end_to_end_auto_approve(tmp_path):
    # Setup test workspace
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text(
        "import os\n"
        "def compute_score():\n"
        "    return os.getenv('SCORE_KEY', 'default_val')\n",
        encoding="utf-8"
    )

    graph = build_docagent_graph()
    initial_state = {
        "job_id": "test-job-1",
        "repo_root": str(tmp_path),
        "trigger_source": "test",
        "auto_approve": True,
    }

    config = {"configurable": {"thread_id": "thread-1"}}
    final_state = graph.invoke(initial_state, config=config)

    assert final_state["status"] == "COMPLETED"
    assert final_state["approval_status"] == "APPROVED"
    assert final_state["inventory"] is not None
    assert len(final_state["proposed_changes"]) >= 1

    # Verify that README.md was physically written to disk
    readme_path = tmp_path / "README.md"
    assert readme_path.is_file()
    assert "# " in readme_path.read_text(encoding="utf-8")

    # Verify execution history trace
    nodes_executed = [h["node"] for h in final_state["execution_history"]]
    assert "validate_request" in nodes_executed
    assert "build_code_inventory" in nodes_executed
    assert "generate_proposed_changes" in nodes_executed
    assert "validate_against_source_code" in nodes_executed
    assert "apply_changes" in nodes_executed
    assert "record_execution_history" in nodes_executed


def test_workflow_human_approval_pause(tmp_path):
    # Setup workspace
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")

    graph = build_docagent_graph()
    initial_state = {
        "job_id": "test-job-pause",
        "repo_root": str(tmp_path),
        "trigger_source": "test",
        "auto_approve": False,  # Requires human review
    }

    config = {"configurable": {"thread_id": "thread-2"}}
    state = graph.invoke(initial_state, config=config)

    # Should pause with WAITING_APPROVAL status and not write files
    assert state["status"] == "WAITING_APPROVAL"
    readme_path = tmp_path / "README.md"
    assert not readme_path.is_file()


def test_workflow_invalid_repo_fails_gracefully():
    graph = build_docagent_graph()
    initial_state = {
        "job_id": "invalid-job",
        "repo_root": "d:/nonexistent_directory_for_testing",
        "trigger_source": "test",
    }

    config = {"configurable": {"thread_id": "thread-3"}}
    state = graph.invoke(initial_state, config=config)

    assert state["status"] == "FAILED"
    assert "does not exist or is invalid" in state["error_message"]
