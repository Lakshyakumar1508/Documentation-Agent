"""Unit tests for Phase 5: Multi-source Log Analyzer and Error Clustering."""

from pathlib import Path
import pytest

from docagent.analyzer.log_analyzer import LogAnalyzer
from docagent.analyzer.models import LogLevel


SAMPLE_PYTHON_LOG = """
2026-11-24 10:00:00 [INFO] Server started on port 8000
2026-11-24 10:01:00 [ERROR] Database connection failed for user admin:password123
Traceback (most recent call last):
  File "src/database.py", line 45, in connect
    raise ConnectionRefusedError("Connection refused by host db.internal")
ConnectionRefusedError: Connection refused by host db.internal
2026-11-24 10:01:05 [ERROR] Retry failed
Traceback (most recent call last):
  File "src/database.py", line 45, in connect
    raise ConnectionRefusedError("Connection refused by host db.internal")
ConnectionRefusedError: Connection refused by host db.internal
"""

SAMPLE_JS_LOG = """
TypeError: Cannot read properties of undefined (reading 'token')
    at authenticate (src/auth.js:24:10)
    at router (src/server.js:50:5)
"""


def test_python_traceback_parsing_and_clustering():
    analyzer = LogAnalyzer()
    res = analyzer.analyze_log_content(SAMPLE_PYTHON_LOG)

    assert res.error_count == 2
    assert len(res.clusters) == 1  # Both tracebacks share the same signature

    cluster = res.clusters[0]
    assert cluster.error_type == "ConnectionRefusedError"
    assert cluster.occurrences == 2
    assert "src/database.py" in cluster.affected_files

    # Check observed facts
    assert len(res.observed_facts) == 1
    assert "ConnectionRefusedError" in res.observed_facts[0]
    assert "2 occurrence" in res.observed_facts[0]

    # Check inferred recommendations
    assert any("port bindings" in r for r in res.inferred_recommendations)


def test_secret_redaction_in_logs():
    analyzer = LogAnalyzer()
    res = analyzer.analyze_log_content(SAMPLE_PYTHON_LOG)

    # password123 should be redacted
    for cluster in res.clusters:
        assert "password123" not in cluster.sample_stack_trace
        assert "password123" not in cluster.representative_message


def test_javascript_error_parsing():
    analyzer = LogAnalyzer()
    res = analyzer.analyze_log_content(SAMPLE_JS_LOG)

    assert res.error_count == 1
    assert len(res.clusters) == 1
    cluster = res.clusters[0]
    assert cluster.error_type == "TypeError"
    assert "src/auth.js" in cluster.affected_files


def test_render_troubleshooting_guide():
    analyzer = LogAnalyzer()
    res = analyzer.analyze_log_content(SAMPLE_PYTHON_LOG)
    proposal = analyzer.render_troubleshooting_guide(res)

    assert proposal.file_path == "docs/troubleshooting.md"
    assert "# Troubleshooting & Operational Guide" in proposal.proposed_content
    assert "ConnectionRefusedError" in proposal.proposed_content
    assert "2 occurrences" in proposal.proposed_content
    assert len(proposal.evidence_anchors) > 0
