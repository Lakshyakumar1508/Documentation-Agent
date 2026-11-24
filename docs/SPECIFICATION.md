# Requirements Specification: Intelligent Documentation Agent

## 1. Executive Summary & Problem Statement
Technical documentation in fast-moving software projects is notoriously prone to drift:
- Codebases evolve while README files, API references, configuration guides, and architectural decisions stay stale.
- Existing tools either rely on naive LLM summarization (which hallucinates non-existent parameters, functions, and endpoints) or rigid AST docstring extractors (which lack high-level architectural insight, rationale, and cross-module context).
- Logs and CI/CD runs reveal real operational reality (failures, common crashes, environment oversights), but this knowledge is rarely synthesized back into troubleshooting and onboarding guides.

The **Intelligent Documentation Agent (DocAgent)** is a production-grade, multi-interface system engineered to analyze repositories deterministically using code parsers (AST and Tree-sitter), calculate Git changes, inspect application & CI logs, and orchestrate controlled documentation generation and drift verification with evidence grounding.

---

## 2. System Goals & Non-Goals

### Goals
1. **Evidence-First Documentation**: Every generated claim must link back to code definitions (file path, line number, symbol name) or verified execution logs.
2. **Review-First Policy**: Modifications are presented as structured diffs with rationale and provenance. Unapproved changes are never merged directly to default branches.
3. **Triple Integration**: A single unified documentation engine powers:
   - GitHub App (webhooks, automated PR creation with evidence summaries).
   - VS Code Extension (workspace-aware interactive commands and diff review).
   - Local CLI (`docagent` commands for terminal workflows, pre-commit, and CI/CD pipelines).
4. **Multi-Language Extensibility**: Native, production-ready support for Python and JavaScript/TypeScript, designed with pluggable grammar parsers for future languages (Go, Rust, Java).
5. **Operational Log Intelligence**: Parse, sanitize, and aggregate execution logs to update troubleshooting docs without treating runtime errors as architectural specifications.
6. **Strict Security Posture**: Constant webhook signature verification, path traversal prevention, zero repo code execution during analysis, automated secret redaction, and strict input sanitization against prompt injection.

### Non-Goals
1. **Autonomous Commits to Production/Default Branches**: The agent never pushes directly to `main`/`master`.
2. **Arbitrary Code Execution**: The agent never runs untrusted repository code just to determine its imports or classes.
3. **Black-Box Autonomous Loops**: Avoid unbounded LLM reasoning loops. All workflow decisions follow an explicit, checkpointable LangGraph directed acyclic graph (DAG).

---

## 3. Functional Requirements

### FR-1: Repository Analyzer & Code Inventory
- **FR-1.1**: Recursively scan workspace directories respecting `.gitignore`, `.docagentignore`, and default exclude rules (`.git`, `node_modules`, `venv`, `__pycache__`, `.pytest_cache`, `dist`, `build`, `.env*`).
- **FR-1.2**: Generate a structured `CodeInventory` capturing:
  - Files, module names, packages, file sizes, language tags, and entry points.
  - Classes, methods, functions, arguments, return type annotations, docstrings.
  - Exported members, import statements, external package dependencies.
  - API route declarations (FastAPI, Flask, Express, NestJS).
  - Environment variable references and configuration schemas.
- **FR-1.3**: Produce deterministic hashes for inventory snapshots to avoid redundant processing.

### FR-2: Code Understanding Engine
- **FR-2.1**: Language-specific parsing using Python `ast` for Python files and `tree-sitter` for JavaScript/TypeScript.
- **FR-2.2**: Pluggable parser registry pattern allowing new language extractors without core engine refactoring.
- **FR-2.3**: Graceful syntax error handling: malformed source files flag syntax warnings without terminating repository-wide analysis.

### FR-3: Git Change Analyzer
- **FR-3.1**: Inspect Git repository state: working tree status, branch comparisons, commit ranges, and unified diffs.
- **FR-3.2**: Classify file changes (Added, Modified, Deleted, Renamed) and map AST diffs to affected symbols (e.g. function signature altered, parameter removed).
- **FR-3.3**: Detect potential breaking changes (removed public functions, altered endpoint routes, changed configuration variables).
- **FR-3.4**: Idempotent event handling: maintain processed commit SHA cache to prevent duplicate webhook processing.

### FR-4: Multi-Source Log Analyzer
- **FR-4.1**: Ingest Python tracebacks, Node.js uncaught exceptions, and GitHub Actions CI workflow logs.
- **FR-4.2**: Extract structured log records: timestamps, severity (INFO/WARN/ERROR/FATAL), error types, normalized stack frames, and correlation IDs.
- **FR-4.3**: Cluster repetitive error signatures using fingerprinting (normalized stack trace hashing).
- **FR-4.4**: Ground operational troubleshooting: generate troubleshooting guidance rooted solely in observed errors, explicitly separating observed runtime facts from inferred root causes.

### FR-5: Documentation Generator
- **FR-5.1**: Generate standard documentation artifacts:
  - `README.md` (Overview, Quickstart, Architecture, Project Structure, Commands).
  - `docs/architecture.md` (System components, data flows, tech stack).
  - `docs/api_reference.md` (Endpoints, parameters, schemas, authentication).
  - `docs/configuration.md` (Environment variables, settings, defaults).
  - `docs/troubleshooting.md` (Common runtime failures, resolution steps).
  - `CHANGELOG.md` (Semantic change summaries organized by release/commit range).
- **FR-5.2**: Modular section generation: allow updating individual sections without overwriting user-curated custom prose.

### FR-6: Consistency Checker & Drift Detection
- **FR-6.1**: Parse existing documentation to extract asserted claims (e.g. referenced CLI commands, documented functions, API endpoints, environment variables).
- **FR-6.2**: Cross-reference asserted claims against the active `CodeInventory`.
- **FR-6.3**: Detect discrepancies:
  - Undocumented public functions/endpoints.
  - Non-existent documented parameters/routes (documentation drift/hallucination).
  - Deprecated or missing configuration variables.
  - Stale dependencies in installation instructions.
- **FR-6.4**: Issue `ValidationFinding` items with confidence scores, severity (`BLOCKER`, `WARNING`, `INFO`), and exact file/line evidence.

### FR-7: LangGraph Controlled Orchestration
- **FR-7.1**: Orchestrate pipeline through typed `DocAgentState` with clear transitions:
  `START -> ValidateRequest -> IdentifyRepo -> ScanRepo -> BuildInventory -> CollectGitChanges -> CollectLogs -> RetrieveExistingDocs -> IdentifyDocImpact -> GenerateProposedChanges -> ValidateAgainstCode -> CheckClaims -> HumanApproval -> ApplyChanges -> RecordHistory -> END`.
- **FR-7.2**: Bounded retries for LLM formatting errors or validation failure loops (maximum 2 retries per node).
- **FR-7.3**: Checkpoint state persistence supporting async human approval interrupts.

### FR-8: Integrations
- **FR-8.1**: **GitHub App Integration**:
  - Secure webhook reception with HMAC-SHA256 signature verification (`X-Hub-Signature-256`).
  - GitHub App JWT token generation and installation access token rotation.
  - Dedicated documentation branch creation (`docagent/update-<timestamp>`).
  - Automated Pull Request creation with evidence table and drift summary.
- **FR-8.2**: **VS Code Extension**:
  - Commands for Project Analysis, README Generation, Log Analysis, Consistency Check, and Change Review.
  - Side panel tree-view displaying inventory, validation findings, and diff viewer.
  - Communication with backend via REST API or local sub-process.
- **FR-8.3**: **CLI (`docagent`)**:
  - Self-contained command-line interface with subcommands: `init`, `analyze`, `generate`, `validate`, `logs`, `watch`.
  - Rich terminal output with progress indicators, formatted tables, and colored diffs.
  - Standalone operation requiring zero external database setup (using SQLite by default).

---

## 4. Non-Functional Requirements (NFR)
- **NFR-1 (Security)**: Redact API keys, tokens, passwords, and private certificates before log parsing or LLM prompt building. Zero execution of repository scripts.
- **NFR-2 (Reliability)**: Deterministic fallbacks for all structural analysis; LLM is only utilized for synthesis and phrasing, never for basic AST symbol extraction.
- **NFR-3 (Performance)**: Local repository scan of a 1,000-file project completes AST parsing in under 5 seconds.
- **NFR-4 (Portability)**: Cross-platform support for Windows, Linux, and macOS.
