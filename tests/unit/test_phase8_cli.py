"""Unit tests for Phase 8: DocAgent CLI."""

from pathlib import Path
import pytest
from typer.testing import CliRunner

from docagent.cli.main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Intelligent Documentation Agent CLI" in result.stdout
    assert "init" in result.stdout
    assert "analyze" in result.stdout
    assert "generate" in result.stdout
    assert "validate" in result.stdout
    assert "logs" in result.stdout
    assert "watch" in result.stdout


def test_cli_init_command(tmp_path):
    result = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "DocAgent successfully initialized" in result.stdout

    ignore_file = tmp_path / ".docagentignore"
    assert ignore_file.is_file()
    assert "node_modules" in ignore_file.read_text(encoding="utf-8")
    assert (tmp_path / "docs").is_dir()


def test_cli_analyze_command(tmp_path):
    # Setup test file
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "api.py").write_text(
        "import os\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/api/v1/ping')\n"
        "def ping():\n"
        "    token = os.getenv('PING_KEY')\n"
        "    return 'pong'\n",
        encoding="utf-8"
    )

    result = runner.invoke(app, ["analyze", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Repository Analysis" in result.stdout
    assert "GET" in result.stdout
    assert "/api/v1/ping" in result.stdout
    assert "PING_KEY" in result.stdout


def test_cli_generate_command_auto_approve(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "math.py").write_text("def multiply(a: int, b: int) -> int: return a * b\n", encoding="utf-8")

    result = runner.invoke(app, ["generate", "--path", str(tmp_path), "--yes"])
    assert result.exit_code == 0
    assert "Generated" in result.stdout
    assert "Changes automatically applied (--yes)" in result.stdout

    readme_file = tmp_path / "README.md"
    assert readme_file.is_file()
    assert "multiply" in readme_file.read_text(encoding="utf-8")


def test_cli_validate_command_clean_repo(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.py").write_text("def start(): pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project\nFunction `start` initializes the system.\n", encoding="utf-8")

    result = runner.invoke(app, ["validate", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "All documentation claims are verified" in result.stdout


def test_cli_validate_command_with_drift(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.py").write_text("def start(): pass\n", encoding="utf-8")
    # Claims a non-existent API route
    (tmp_path / "README.md").write_text("Call `GET /api/v1/ghost` for metrics.\n", encoding="utf-8")

    result = runner.invoke(app, ["validate", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "CRITICAL" in result.stdout
    assert "incorrect_api_route" in result.stdout


def test_cli_logs_command(tmp_path):
    log_file = tmp_path / "error.log"
    log_file.write_text(
        "2026-11-24 10:00:00 [ERROR] Crash\n"
        "Traceback (most recent call last):\n"
        "  File 'app.py', line 10, in run\n"
        "    raise RuntimeError('Fatal error')\n"
        "RuntimeError: Fatal error\n",
        encoding="utf-8"
    )

    result = runner.invoke(app, ["logs", str(log_file)])
    assert result.exit_code == 0
    assert "Log Analysis Summary" in result.stdout
    assert "RuntimeError" in result.stdout

