"""Unit tests for Phase 1: Security, Scanner, AST, and Tree-sitter Inventory."""

import os
from pathlib import Path
import pytest

from docagent.analyzer.ast_parser import PythonASTParser
from docagent.analyzer.inventory_builder import InventoryBuilder
from docagent.analyzer.models import SymbolKind
from docagent.analyzer.repo_scanner import RepoScanner
from docagent.analyzer.treesitter_engine import TreeSitterEngine
from docagent.core.exceptions import PathTraversalError
from docagent.security.path_validator import validate_contained_path
from docagent.security.redaction import RedactionEngine


def test_path_validator_contained(tmp_path):
    sub_file = tmp_path / "src" / "app.py"
    sub_file.parent.mkdir(parents=True)
    sub_file.write_text("print('hello')", encoding="utf-8")

    # Contained path succeeds
    validated = validate_contained_path(tmp_path, sub_file)
    assert validated.exists()
    assert str(validated).startswith(str(tmp_path.resolve()))


def test_path_validator_traversal_blocked(tmp_path):
    # Attempt to breach base directory
    with pytest.raises(PathTraversalError):
        validate_contained_path(tmp_path, tmp_path / ".." / "outside.txt")


def test_secret_redaction():
    text = (
        "Encountered error with key AKIA1234567890ABCDEF and GitHub token "
        "ghp_abcdefghijklmnopqrstuvwxyz1234567890. "
        "Connect string: postgres://admin:super_secret_pw@db.internal:5432/main. "
        "Auth header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
    )
    redacted = RedactionEngine.redact_text(text)

    assert "AKIA1234567890ABCDEF" not in redacted
    assert "[REDACTED:AWS_KEY]" in redacted
    assert "ghp_abcdefghijklmnopqrstuvwxyz1234567890" not in redacted
    assert "[REDACTED:GITHUB_TOKEN]" in redacted
    assert "super_secret_pw" not in redacted
    assert "[REDACTED:PASSWORD]" in redacted
    assert "[REDACTED:BEARER_TOKEN]" in redacted


def test_python_ast_parser():
    code = '''
"""Module docstring."""
import os
from typing import Optional

def calculate_metric(alpha: float, beta: int = 10) -> float:
    """Calculate the alpha-beta metric."""
    token = os.getenv("METRIC_API_KEY", "default_key")
    return alpha * beta

class ServiceClient:
    """Client for interacting with services."""
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def get_data(self, query: str) -> dict:
        return {"query": query}
'''
    parser = PythonASTParser("test_module.py", code)
    symbols, routes, configs, imports = parser.parse()

    assert "os" in imports
    assert "typing" in imports

    # Check symbols
    func_sym = next(s for s in symbols if s.name == "calculate_metric")
    assert func_sym.kind == SymbolKind.FUNCTION
    assert len(func_sym.parameters) == 2
    assert func_sym.parameters[0].name == "alpha"
    assert func_sym.parameters[0].type_annotation == "float"
    assert func_sym.parameters[1].default_value == "10"
    assert func_sym.return_type == "float"

    class_sym = next(s for s in symbols if s.name == "ServiceClient")
    assert class_sym.kind == SymbolKind.CLASS

    method_sym = next(s for s in symbols if s.name == "get_data")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_class == "ServiceClient"
    assert method_sym.is_async is True

    # Check config
    cfg = next(c for c in configs if c.key == "METRIC_API_KEY")
    assert cfg.default_value == "default_key"
    assert cfg.is_secret is True


def test_fastapi_route_detection():
    code = '''
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

@router.get("/api/v1/users/{user_id}")
async def get_user(user_id: int):
    return {"id": user_id}

@app.post("/api/v1/users")
def create_user(data: dict):
    return data
'''
    parser = PythonASTParser("api_routes.py", code)
    symbols, routes, configs, imports = parser.parse()

    assert len(routes) == 2
    get_route = next(r for r in routes if r.http_method == "GET")
    assert get_route.path == "/api/v1/users/{user_id}"
    assert get_route.handler_name == "get_user"

    post_route = next(r for r in routes if r.http_method == "POST")
    assert post_route.path == "/api/v1/users"
    assert post_route.handler_name == "create_user"


def test_treesitter_js_ts_parser():
    ts_code = '''
import { Request, Response } from "express";

export interface UserProfile {
    id: string;
    email: string;
}

export class UserManager {
    private apiKey = process.env.USER_SERVICE_KEY;

    public getUser(id: string): UserProfile {
        return { id, email: "user@example.com" };
    }
}

export const helper = (msg: string) => {
    return msg.toUpperCase();
};
'''
    engine = TreeSitterEngine()
    symbols, routes, configs, imports = engine.parse_file("user.ts", ts_code, language="typescript")

    # Verify interface
    iface = next((s for s in symbols if s.name == "UserProfile"), None)
    assert iface is not None
    assert iface.kind == SymbolKind.INTERFACE

    # Verify class & method
    cls_sym = next((s for s in symbols if s.name == "UserManager"), None)
    assert cls_sym is not None
    assert cls_sym.kind == SymbolKind.CLASS

    method_sym = next((s for s in symbols if s.name == "getUser"), None)
    assert method_sym is not None
    assert method_sym.parent_class == "UserManager"

    # Verify arrow function
    helper_sym = next((s for s in symbols if s.name == "helper"), None)
    assert helper_sym is not None
    assert helper_sym.kind == SymbolKind.FUNCTION

    # Verify config
    cfg = next((c for c in configs if c.key == "USER_SERVICE_KEY"), None)
    assert cfg is not None
    assert cfg.is_secret is True


def test_repo_scanner_exclusions(tmp_path):
    # Setup dummy project files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.py").write_text("# entry", encoding="utf-8")
    
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "pip.py").write_text("# ignored", encoding="utf-8")
    
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("// ignored", encoding="utf-8")

    (tmp_path / "requirements.txt").write_text("fastapi>=0.110.0\npydantic==2.6.0\n", encoding="utf-8")

    scanner = RepoScanner(tmp_path)
    files = scanner.scan_files()
    rel_paths = [f.relative_path.replace("\\", "/") for f in files]

    assert "src/index.py" in rel_paths
    assert "requirements.txt" in rel_paths
    assert not any(".venv" in p for p in rel_paths)
    assert not any("node_modules" in p for p in rel_paths)

    deps = scanner.extract_dependencies()
    dep_names = [d.name for d in deps]
    assert "fastapi" in dep_names
    assert "pydantic" in dep_names


def test_inventory_builder(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text(
        "import os\n"
        "def run():\n"
        "    return os.getenv('APP_ENV', 'dev')\n",
        encoding="utf-8"
    )

    builder = InventoryBuilder(tmp_path)
    inventory = builder.build()

    assert inventory.total_files >= 1
    assert any(s.name == "run" for s in inventory.symbols)
    assert any(c.key == "APP_ENV" for c in inventory.configs)
    assert "src/main.py" in inventory.entry_points
