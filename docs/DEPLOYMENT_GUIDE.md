# Deployment Guide: Intelligent Documentation Agent

## 1. Local Developer Setup

### Prerequisites
- Python 3.10+
- Git 2.30+
- Node.js 18+ (for VS Code extension development)

### Quickstart
```bash
# 1. Clone repository and set up virtual environment
git clone <repo-url>
cd "Documentation Agent"
python -m venv .venv

# 2. Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# On Linux/macOS: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -e . --no-deps

# 4. Copy configuration
cp .env.example .env

# 5. Run DocAgent CLI
docagent --help
docagent analyze
```

---

## 2. Docker & Container Deployment

### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e . --no-deps

COPY . .

EXPOSE 8000

CMD ["uvicorn", "docagent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  docagent-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://postgres:secret@db:5432/docagent
      - GITHUB_APP_ID=${GITHUB_APP_ID}
      - GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET}
      - LLM_PROVIDER=openai
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=docagent
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=secret
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

---

## 3. GitHub App Configuration

To enable automated Pull Request creation and webhook monitoring:
1. Navigate to **GitHub Settings -> Developer Settings -> GitHub Apps -> New GitHub App**.
2. **Webhook URL**: `https://<your-docagent-domain>/api/v1/webhooks/github`
3. **Webhook Secret**: Generate a cryptographically strong string and add to `GITHUB_WEBHOOK_SECRET`.
4. **Permissions**:
   - `Repository contents`: Read & Write (for creating documentation branches and PRs).
   - `Pull requests`: Read & Write.
   - `Workflows / Actions`: Read-only (for CI log inspection).
   - `Metadata`: Read-only.
5. **Events**:
   - Check `Push`, `Pull request`, `Workflow run`.
6. **Generate Private Key**: Download `.pem` private key and set path in `GITHUB_APP_PRIVATE_KEY`.

