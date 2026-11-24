# Known Limitations & Future Improvements

## 1. Known Limitations

1. **Dynamic Route Construction**:
   - The AST and Tree-sitter parsers statically identify standard decorator-based and call-based routes (FastAPI, Flask, Express, NestJS). Endpoints constructed dynamically at runtime through loops or reflection are not detected.
   - *Mitigation*: OpenAPI schema integration allows falling back to exported `openapi.json` files when available.

2. **Language Coverage**:
   - Currently provides native, tested support for Python (AST) and JavaScript / TypeScript (Tree-sitter).
   - Additional languages (Go, Rust, Java, C#) will be supported via tree-sitter grammar extensions.

3. **Log Size Limits**:
   - Raw logs exceeding 50 MB are clipped to safeguard memory usage and prevent Denial of Service.

---

## 2. Planned Future Improvements

1. **Semantic Vector Indexing (pgvector / ChromaDB)**:
   - For multi-million-line monorepositories, index module docstrings and symbols in vector storage for instant semantic querying during documentation generation.

2. **Interactive VS Code Custom Webview**:
   - Replace standard text channel outputs with a rich visual sidebar displaying live dependency graphs, route tables, and one-click inline patch reviews.

3. **ChatOps & Slack / Discord Approval Hooks**:
   - Allow engineers to review and approve documentation changes directly from Slack channels (`/docagent approve <job_id>`).

4. **Additional Language Parsers**:
   - Expand Tree-sitter query sets to natively support Go (`net/http`, `gin-gonic`), Rust (`actix-web`, `axum`), and Java (`Spring Boot`).

