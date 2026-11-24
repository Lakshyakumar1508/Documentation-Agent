# Implementation Roadmap & Risk Management: Intelligent Documentation Agent

## 1. Incremental Execution Roadmap

The implementation follows a strict 10-phase architecture. After every phase, unit tests and validation are executed:

- **Phase 1: Local Repository Scanning & Code Inventory**
  - Path traversal guardrails and `.gitignore` file walker.
  - Python AST extractor (functions, classes, args, returns, docstrings, dependencies, FastAPI/Flask routes).
  - TypeScript/JavaScript Tree-sitter extractor (interfaces, classes, functions, exports, Express/Nest routes).
  - Serialized `CodeInventory` data contracts.

- **Phase 2: Git Diff & Change Analysis**
  - Git status, branch, and commit unified diff parsing.
  - File status classification (Added, Modified, Deleted, Renamed).
  - AST-to-diff symbol mapping (linking line ranges to modified symbols).
  - Breaking API change detector.

- **Phase 3: Documentation Generation Engine**
  - Pluggable LLM client abstraction (NVIDIA API / OpenAI compatible).
  - Template and prompt engines for README, Architecture, API Reference, Config Reference, and Changelog.
  - Strict evidence grounding (embedding code provenance anchors).

- **Phase 4: Evidence-Based Validation & Drift Detection**
  - Markdown claim extractor (symbols, parameters, routes, env vars).
  - Verification against active `CodeInventory`.
  - Severity-graded `ValidationFinding` reports (Missing Symbol, Obsolete Route, Mismatched Argument).

- **Phase 5: Multi-Source Log Analyzer**
  - Python stack trace parser and Node.js exception parser.
  - CI workflow log interpreter.
  - Error deduplication, clustering, and frequency analysis.
  - Generation of evidence-grounded Troubleshooting guides.

- **Phase 6: LangGraph Controlled Orchestration**
  - Typed `DocAgentState` schema.
  - Nodes: Validate, Scan, Inventory, GitDiff, LogAnalyze, RetrieveDocs, Synthesize, ValidateCode, CheckClaims, HumanApproval, ApplyChanges.
  - Bounded retries (max 2 cycles), checkpoints, and cancellation handlers.

- **Phase 7: FastAPI Backend & GitHub App Integration**
  - Asynchronous FastAPI service with SQLite/Postgres support.
  - GitHub webhook signature verification (`X-Hub-Signature-256`).
  - GitHub App token generation and Pull Request creation on dedicated branches.

- **Phase 8: CLI (`docagent`)**
  - Typer CLI with commands: `init`, `analyze`, `generate`, `validate`, `logs`, `watch`.
  - Rich formatting: terminal diffs, summary tables, and real-time watcher.

- **Phase 9: VS Code Extension**
  - TypeScript extension with Extension API integration.
  - Commands: Analyze Project, Generate README, Analyze Logs, Check Documentation, Review Changes.
  - Webview/Sidebar review panel for diffs and one-click approvals.

- **Phase 10: Production Hardening, Monitoring & Full Verification**
  - Comprehensive test suite (unit, integration, end-to-end).
  - Observability metrics (job duration, token usage, validation pass rates).
  - Final documentation deliverables.

---

## 2. Key Assumptions
1. Repositories provide a standard file layout or recognizable source directories (`src/`, `lib/`, `app/`, etc.).
2. Python source files can be parsed using Python 3.10 AST; JavaScript/TypeScript files can be parsed using Tree-sitter grammar without needing a Node runtime for AST extraction.
3. For environments without an active LLM API key, deterministic fallback generators provide high-quality structural markdown directly from the AST inventory.

## 3. Critical Risks & Mitigation Strategies
1. **Risk: LLM Hallucination of Parameters or Endpoints**
   - *Mitigation*: The Generator is constrained by strict JSON/Markdown schema with symbol constraints, and Phase 4 Consistency Checker flags any claim not present in the AST inventory.
2. **Risk: Prompt Injection in Source Files or PR Diffs**
   - *Mitigation*: Code snippets and diffs are wrapped in structural delimiters, and system prompts explicitly forbid following commands embedded inside source blocks.
3. **Risk: Secret Leakage in Logs**
   - *Mitigation*: The `RedactionEngine` scrubs all input strings before they touch any database, analyzer, or prompt payload.
4. **Risk: Infinite Agent Loops**
   - *Mitigation*: LangGraph is configured as an acyclic state machine with a hard retry ceiling of 2 on validation failures.
