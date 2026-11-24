# API Specification: DocAgent REST & Webhook Interfaces

## 1. Overview
DocAgent provides an OpenAPI-compliant REST API developed with FastAPI. The service handles incoming GitHub App webhooks, serves the VS Code extension, and orchestrates documentation analysis jobs.

- **Base URL**: `http://localhost:8000/api/v1`
- **Authentication**: HMAC-SHA256 signature verification for webhooks; Bearer token authentication for management endpoints.

---

## 2. Endpoints

### 2.1 System Health
```http
GET /healthz
```
- **Description**: Lightweight health probe for Kubernetes liveness/readiness probes.
- **Response**: `200 OK`
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "0.1.0"
}
```

---

### 2.2 GitHub Webhook Ingestion
```http
POST /api/v1/webhooks/github
```
- **Description**: Secure receiver for GitHub App webhook events (`push`, `pull_request`, `workflow_run`).
- **Headers**:
  - `X-GitHub-Event`: Event name (e.g., `push`)
  - `X-GitHub-Delivery`: Unique UUID for idempotency
  - `X-Hub-Signature-256`: `sha256=<hmac_sha256_hex_digest>`
- **Response**:
  - `202 Accepted`: Event queued for processing
  - `401 Unauthorized`: Webhook signature mismatch
```json
{
  "status": "accepted",
  "event": "push",
  "delivery_id": "7b8e1f54-b4a8-4444-a90f-90eef5cbb291"
}
```

---

### 2.3 Documentation Jobs

#### Trigger Job
```http
POST /api/v1/jobs
```
- **Request Body**:
```json
{
  "repo_root": "d:/Coding Space/MyProject",
  "trigger_source": "vscode",
  "base_ref": "v1.0.0",
  "head_ref": "v2.0.0",
  "auto_approve": false
}
```
- **Response**: `201 Created`
```json
{
  "job_id": "e63a5ef1-a3f2-4bd5-9ce2-68c67c515714",
  "status": "WAITING_APPROVAL",
  "approval_status": "PENDING",
  "proposed_changes_count": 3
}
```

#### Query Job Details
```http
GET /api/v1/jobs/{job_id}
```
- **Response**: `200 OK`
```json
{
  "job_id": "e63a5ef1-a3f2-4bd5-9ce2-68c67c515714",
  "status": "WAITING_APPROVAL",
  "approval_status": "PENDING",
  "proposed_changes": [
    {
      "file_path": "README.md",
      "doc_type": "readme",
      "unified_diff": "--- a/README.md\n+++ b/README.md\n@@ ...",
      "rationale": "Updated with newly discovered API routes.",
      "is_new_file": false
    }
  ],
  "validation_report": {
    "is_valid": true,
    "critical_count": 0,
    "warning_count": 0,
    "findings": []
  },
  "execution_history": [
    { "node": "validate_request", "status": "SUCCESS" },
    { "node": "build_code_inventory", "files_indexed": 42 }
  ]
}
```

#### Approve / Reject Job
```http
POST /api/v1/jobs/{job_id}/approve
```
- **Request Body**:
```json
{
  "decision": "APPROVED",
  "reviewer_notes": "All diffs verified against v2 routes."
}
```
- **Response**: `200 OK`
```json
{
  "job_id": "e63a5ef1-a3f2-4bd5-9ce2-68c67c515714",
  "status": "COMPLETED",
  "approval_status": "APPROVED"
}
```

---

### 2.4 On-Demand Consistency Verification
```http
POST /api/v1/jobs/validation/check
```
- **Request Body**:
```json
{
  "repo_root": "d:/Coding Space/MyProject"
}
```
- **Response**: `200 OK`
```json
{
  "repo_name": "MyProject",
  "total_files": 42,
  "is_valid": false,
  "critical_count": 1,
  "warning_count": 0,
  "findings": [
    {
      "rule": "incorrect_api_route",
      "severity": "critical",
      "doc_file": "README.md",
      "line_number": 34,
      "claim": "GET /api/v1/ghost",
      "message": "Documented route 'GET /api/v1/ghost' does not exist in active code.",
      "suggested_fix": "Verify route path and HTTP method in router definitions."
    }
  ]
}
```

