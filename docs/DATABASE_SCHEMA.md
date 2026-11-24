# Database Schema & Data Models: Intelligent Documentation Agent

## 1. Overview
The persistence layer supports both PostgreSQL (for production multi-tenant GitHub App deployment) and SQLite (for local single-user CLI and offline VS Code execution) using SQLAlchemy 2.0 ORM with asynchronous capabilities (`aiosqlite` and `asyncpg`).

---

## 2. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    User ||--o{ RepositoryInstallation : owns
    RepositoryInstallation ||--o{ Repository : manages
    Repository ||--o{ GitEvent : triggers
    Repository ||--o{ AnalysisJob : executes
    Repository ||--o{ DocumentationFile : contains
    
    AnalysisJob ||--o{ CodeInventorySnapshot : produces
    AnalysisJob ||--o{ LogAnalysisResult : analyzes
    AnalysisJob ||--o{ DocumentationChange : proposes
    AnalysisJob ||--o{ ValidationFinding : identifies
    AnalysisJob ||--o{ ApprovalRecord : requires
    AnalysisJob ||--o{ AgentExecutionStep : records

    DocumentationChange ||--o{ ApprovalRecord : evaluated_by

    User {
        uuid id PK
        string username
        string email
        string hashed_password
        string role
        timestamp created_at
    }

    RepositoryInstallation {
        uuid id PK
        uuid user_id FK
        string provider
        string installation_id
        jsonb permissions
        timestamp installed_at
    }

    Repository {
        uuid id PK
        uuid installation_id FK
        string full_name
        string default_branch
        string local_path
        boolean is_active
        timestamp created_at
    }

    AnalysisJob {
        uuid id PK
        uuid repository_id FK
        string trigger_source
        string commit_sha
        string target_branch
        string status
        jsonb config_overrides
        timestamp started_at
        timestamp completed_at
    }

    CodeInventorySnapshot {
        uuid id PK
        uuid job_id FK
        string commit_sha
        jsonb files_inventory
        jsonb symbols_index
        jsonb api_routes
        timestamp captured_at
    }

    DocumentationChange {
        uuid id PK
        uuid job_id FK
        string file_path
        string change_type
        text original_content
        text proposed_content
        text unified_diff
        text rationale
        jsonb evidence_references
        string status
        timestamp created_at
    }

    ValidationFinding {
        uuid id PK
        uuid job_id FK
        string rule_name
        string severity
        string target_file
        integer line_number
        text message
        jsonb evidence
        timestamp detected_at
    }

    LogAnalysisResult {
        uuid id PK
        uuid job_id FK
        string log_source
        integer total_entries
        integer error_count
        jsonb clustered_signatures
        jsonb observed_facts
        timestamp analyzed_at
    }

    ApprovalRecord {
        uuid id PK
        uuid job_id FK
        uuid change_id FK
        string decision
        string reviewer_id
        text feedback_notes
        timestamp decided_at
    }

    AgentExecutionStep {
        uuid id PK
        uuid job_id FK
        string node_name
        integer attempt
        string status
        jsonb inputs_summary
        jsonb outputs_summary
        integer duration_ms
        integer tokens_used
        timestamp executed_at
    }
```

---

## 3. Retention Policies & Indexing
1. **Idempotency Index**: Unique index on `(repository_id, commit_sha, trigger_source)` in `AnalysisJob` to prevent duplicate processing of re-sent webhooks.
2. **Fast Lookup Indexes**:
   - `AnalysisJob(repository_id, status)`
   - `DocumentationChange(job_id, status)`
   - `ValidationFinding(job_id, severity)`
3. **Data Retention**:
   - Intermediate execution step traces are pruned after 30 days.
   - Code inventory snapshots keep the latest 10 snapshots per repository.
   - Documentation change history and approval records are retained indefinitely for auditing.
