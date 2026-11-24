"""Unit and integration tests for Phase 7: FastAPI Backend and GitHub App Integration."""

import hashlib
import hmac
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from docagent.analyzer.models import BreakingChange, BreakingChangeSeverity
from docagent.api.main import app
from docagent.core.config import settings
from docagent.generator.models import DocProposal, DocType, EvidenceAnchor
from docagent.integrations.github_app import GitHubAppClient


client = TestClient(app)


def test_healthz_endpoint():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


def test_webhook_signature_verification():
    secret = "my-test-secret"
    gh_client = GitHubAppClient(webhook_secret=secret)

    payload = b'{"action": "opened"}'
    valid_sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Valid signature succeeds
    assert gh_client.verify_webhook_signature(payload, valid_sig) is True

    # Forged signature fails
    with pytest.raises(Exception):
        gh_client.verify_webhook_signature(payload, "sha256=invalid1234567890abcdef")


def test_webhook_endpoint_hmac_rejection():
    # Attempting to call webhook with invalid signature returns 401
    settings.GITHUB_WEBHOOK_SECRET = "test-secret"
    resp = client.post(
        "/api/v1/webhooks/github",
        json={"action": "push"},
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "deliv-123",
            "X-Hub-Signature-256": "sha256=forged_signature_here",
        }
    )
    assert resp.status_code == 401


def test_webhook_endpoint_accepted():
    secret = "test-secret"
    settings.GITHUB_WEBHOOK_SECRET = secret

    payload_dict = {"action": "push", "repository": {"full_name": "owner/repo"}}
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    resp = client.post(
        "/api/v1/webhooks/github",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "delivery-unique-001",
            "X-Hub-Signature-256": sig,
        }
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_job_trigger_and_approval_cycle(tmp_path):
    # Setup test repo
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "service.py").write_text("def ping(): return 'pong'\n", encoding="utf-8")

    # 1. Trigger job with auto_approve=False
    resp = client.post(
        "/api/v1/jobs",
        json={
            "repo_root": str(tmp_path),
            "trigger_source": "test",
            "auto_approve": False,
        }
    )
    assert resp.status_code == 201
    data = resp.json()
    job_id = data["job_id"]
    assert data["status"] == "WAITING_APPROVAL"

    # 2. Query job details
    get_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert get_resp.status_code == 200
    job_data = get_resp.json()
    assert job_data["status"] == "WAITING_APPROVAL"
    assert len(job_data["proposed_changes"]) >= 1

    # 3. Approve changes
    app_resp = client.post(
        f"/api/v1/jobs/{job_id}/approve",
        json={"decision": "APPROVED", "reviewer_notes": "Looks solid"}
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "COMPLETED"

    # 4. Verify file was applied to disk
    readme_file = tmp_path / "README.md"
    assert readme_file.is_file()


def test_validation_check_endpoint(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.py").write_text("def hello(): pass\n", encoding="utf-8")

    resp = client.post(
        "/api/v1/jobs/validation/check",
        json={"repo_root": str(tmp_path)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "repo_name" in data
    assert "is_valid" in data


def test_pr_formatting_evidence():
    proposals = [
        DocProposal(
            file_path="README.md",
            doc_type=DocType.README,
            proposed_content="# Title",
            evidence_anchors=[EvidenceAnchor(source_file="src/index.py", rationale="Main entry point")],
        )
    ]
    breaking = [
        BreakingChange(
            kind="symbol_removed",
            symbol_name="old_func",
            file_path="src/legacy.py",
            description="Function was deprecated.",
            severity=BreakingChangeSeverity.CRITICAL,
        )
    ]

    pr_body = GitHubAppClient.format_pull_request_body(
        proposals=proposals,
        breaking_changes=breaking,
        commit_sha="abcdef123456"
    )

    assert "README.md" in pr_body
    assert "old_func" in pr_body
    assert "Function was deprecated." in pr_body
    assert "Quality & Security Verification" in pr_body
