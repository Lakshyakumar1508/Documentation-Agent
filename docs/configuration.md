# Configuration & Environment Variable Reference

All environment variables discovered through static code inspection.

| Key | Default | Sensitive | Declared In |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | `'DocAgent'` | No | `docagent/core/config.py` |
| `ENVIRONMENT` | `'development'` | No | `docagent/core/config.py` |
| `DEBUG` | `False` | No | `docagent/core/config.py` |
| `LOG_LEVEL` | `'INFO'` | No | `docagent/core/config.py` |
| `SECRET_KEY` | `'insecure-development-secret-key-change-in-production'` | Yes | `docagent/core/config.py` |
| `ALLOWED_ORIGINS` | `['*']` | No | `docagent/core/config.py` |
| `MAX_FILE_SIZE_BYTES` | `5 * 1024 * 1024` | No | `docagent/core/config.py` |
| `MAX_LOG_SIZE_BYTES` | `50 * 1024 * 1024` | No | `docagent/core/config.py` |
| `MAX_REPO_SCAN_FILES` | `10000` | No | `docagent/core/config.py` |
| `DEFAULT_EXCLUDES` | `['.git', '.venv', 'venv', '__pycache__', 'node_modules', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist', 'build', 'coverage', '.idea', '.vscode', '.DS_Store', 'Thumbs.db', '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll', '*.dylib', '*.exe', '*.bin', '.env*']` | No | `docagent/core/config.py` |
| `DATABASE_URL` | `'sqlite:///docagent.db'` | No | `docagent/core/config.py` |
| `LLM_PROVIDER` | `'openai'` | No | `docagent/core/config.py` |
| `LLM_API_KEY` | `None` | Yes | `docagent/core/config.py` |
| `LLM_BASE_URL` | `None` | No | `docagent/core/config.py` |
| `LLM_MODEL` | `'gpt-4o-mini'` | No | `docagent/core/config.py` |
| `LLM_TEMPERATURE` | `0.1` | No | `docagent/core/config.py` |
| `LLM_MAX_TOKENS` | `4096` | Yes | `docagent/core/config.py` |
| `LLM_TIMEOUT_SECONDS` | `60` | No | `docagent/core/config.py` |
| `GITHUB_APP_ID` | `None` | No | `docagent/core/config.py` |
| `GITHUB_APP_PRIVATE_KEY` | `None` | Yes | `docagent/core/config.py` |
| `GITHUB_WEBHOOK_SECRET` | `None` | Yes | `docagent/core/config.py` |
| `GIT_AUTHOR_NAME` | `'DocAgent Bot'` | No | `docagent/core/config.py` |
| `GIT_AUTHOR_EMAIL` | `'docagent-bot@users.noreply.github.com'` | No | `docagent/core/config.py` |
| `DEFAULT_BRANCH_PREFIX` | `'docagent/update-'` | No | `docagent/core/config.py` |
