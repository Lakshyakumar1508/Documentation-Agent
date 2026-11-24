# API Reference Documentation

This document details verified HTTP endpoints and public API interfaces.

### `POST `

- **Handler**: `trigger_analysis_job`
- **Source**: `docagent/api/routes/jobs.py#L53`
- **Authentication**: None / Optional

### `GET /{job_id}`

- **Handler**: `get_job_details`
- **Source**: `docagent/api/routes/jobs.py#L89`
- **Authentication**: None / Optional

### `POST /{job_id}/approve`

- **Handler**: `approve_job_changes`
- **Source**: `docagent/api/routes/jobs.py#L106`
- **Authentication**: None / Optional

### `POST /validation/check`

- **Handler**: `check_repository_consistency`
- **Source**: `docagent/api/routes/jobs.py#L140`
- **Authentication**: None / Optional

### `POST /github`

- **Handler**: `handle_github_webhook`
- **Source**: `docagent/api/routes/webhooks.py#L37`
- **Authentication**: None / Optional
