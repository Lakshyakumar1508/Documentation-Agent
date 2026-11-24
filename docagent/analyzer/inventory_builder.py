"""Unified CodeInventory builder aggregating filesystem, AST, and Tree-sitter parsers."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from docagent.analyzer.ast_parser import PythonASTParser
from docagent.analyzer.models import CodeInventory
from docagent.analyzer.repo_scanner import RepoScanner
from docagent.analyzer.treesitter_engine import TreeSitterEngine
from docagent.core.logging import logger
from docagent.security.path_validator import validate_contained_path


class InventoryBuilder:
    """Orchestrates multi-language parsing to construct a complete CodeInventory."""

    def __init__(self, repo_root: Path):
        self.repo_root = validate_contained_path(repo_root, repo_root)
        self.treesitter_engine = TreeSitterEngine()

    def build(self) -> CodeInventory:
        """Executes repository scan and static code extraction."""
        logger.info(f"Starting code inventory build for: {self.repo_root}")
        
        scanner = RepoScanner(self.repo_root)
        files = scanner.scan_files()
        dependencies = scanner.extract_dependencies()

        inventory = CodeInventory(
            repo_name=self.repo_root.name,
            repo_root=str(self.repo_root),
            scanned_at=datetime.now(timezone.utc).isoformat(),
            total_files=len(files),
            files=files,
            dependencies=dependencies,
            entry_points=[f.relative_path for f in files if f.is_entry_point],
        )

        for file_desc in files:
            full_path = self.repo_root / file_desc.relative_path
            
            # Read content safely
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    source_code = f.read()
            except Exception as e:
                logger.warning(f"Could not read {file_desc.relative_path}: {e}")
                continue

            # Python AST parsing
            if file_desc.language == "python":
                ast_parser = PythonASTParser(file_desc.relative_path, source_code)
                symbols, routes, configs, imports = ast_parser.parse()
                
                inventory.symbols.extend(symbols)
                inventory.api_routes.extend(routes)
                inventory.configs.extend(configs)
                file_desc.imports = imports
                file_desc.exported_symbols = [s.name for s in symbols if s.is_exported]

            # JavaScript / TypeScript Tree-sitter parsing
            elif file_desc.language in ("javascript", "typescript"):
                try:
                    symbols, routes, configs, imports = self.treesitter_engine.parse_file(
                        rel_path=file_desc.relative_path,
                        source_code=source_code,
                        language=file_desc.language,
                    )
                    inventory.symbols.extend(symbols)
                    inventory.api_routes.extend(routes)
                    inventory.configs.extend(configs)
                    file_desc.imports = imports
                    file_desc.exported_symbols = [s.name for s in symbols if s.is_exported]
                except Exception as e:
                    logger.warning(f"Tree-sitter error on {file_desc.relative_path}: {e}")

        logger.info(
            f"Inventory build complete: {len(inventory.files)} files, "
            f"{len(inventory.symbols)} symbols, {len(inventory.api_routes)} routes, "
            f"{len(inventory.configs)} configs"
        )
        return inventory
