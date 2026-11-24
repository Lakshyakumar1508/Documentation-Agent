"""Repository scanner with path containment, gitignore parsing, and exclusion rules."""

import fnmatch
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import yaml

from docagent.analyzer.models import DependencyDescriptor, FileDescriptor
from docagent.core.config import settings
from docagent.core.logging import logger
from docagent.security.path_validator import validate_contained_path


LANGUAGE_EXTENSION_MAP: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".toml": "toml",
    ".sh": "shell",
    ".bash": "shell",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
}

ENTRY_POINT_CANDIDATES = {
    "main.py",
    "app.py",
    "server.py",
    "index.py",
    "cli.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "main.ts",
    "app.ts",
}


class RepoScanner:
    """Scans and indexes workspace files deterministically."""

    def __init__(
        self,
        repo_root: Path,
        custom_excludes: Optional[List[str]] = None,
        max_files: int = settings.MAX_REPO_SCAN_FILES,
    ):
        self.repo_root = validate_contained_path(repo_root, repo_root)
        self.max_files = max_files
        self.exclude_patterns: List[str] = list(settings.DEFAULT_EXCLUDES)
        if custom_excludes:
            self.exclude_patterns.extend(custom_excludes)
        
        # Load .gitignore and .docagentignore if present
        self._load_ignore_file(".gitignore")
        self._load_ignore_file(".docagentignore")

    def _load_ignore_file(self, filename: str) -> None:
        """Reads patterns from an ignore file in the repo root."""
        ignore_path = self.repo_root / filename
        if ignore_path.is_file():
            try:
                with open(ignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            self.exclude_patterns.append(line)
            except Exception as e:
                logger.warning(f"Failed to read {filename}: {e}")

    def is_excluded(self, rel_path: str) -> bool:
        """Checks if a relative path matches any exclusion pattern."""
        parts = rel_path.replace("\\", "/").split("/")
        rel_str = "/".join(parts)

        for pattern in self.exclude_patterns:
            clean_pat = pattern.rstrip("/").replace("\\", "/")
            # Directory match check
            if any(fnmatch.fnmatch(part, clean_pat) for part in parts):
                return True
            # Glob match check
            if fnmatch.fnmatch(rel_str, clean_pat) or fnmatch.fnmatch(parts[-1], clean_pat):
                return True
        return False

    def scan_files(self) -> List[FileDescriptor]:
        """Discovers and catalogs all valid source files in the repository."""
        file_descriptors: List[FileDescriptor] = []
        count = 0

        for root, dirs, files in os.walk(self.repo_root):
            # Compute relative directory from repo root
            rel_dir = os.path.relpath(root, self.repo_root)
            if rel_dir == ".":
                rel_dir = ""

            # Prune excluded directories in-place to prevent scanning deeper
            dirs[:] = [
                d for d in dirs
                if not self.is_excluded(f"{rel_dir}/{d}" if rel_dir else d)
            ]

            for fname in files:
                rel_file = f"{rel_dir}/{fname}".replace("\\", "/") if rel_dir else fname
                if self.is_excluded(rel_file):
                    continue

                full_path = Path(root) / fname
                try:
                    # Enforce symlink safety and path containment
                    full_path = validate_contained_path(self.repo_root, full_path)
                    
                    file_size = full_path.stat().st_size
                    if file_size > settings.MAX_FILE_SIZE_BYTES:
                        logger.info(f"Skipping oversized file ({file_size} bytes): {rel_file}")
                        continue

                    # Determine language from extension
                    ext = full_path.suffix.lower()
                    language = LANGUAGE_EXTENSION_MAP.get(ext, "unknown")

                    # Skip binary files if unknown
                    if language == "unknown" and self._is_binary_file(full_path):
                        continue

                    # Compute SHA256
                    file_hash = self._compute_hash(full_path)
                    is_entry = fname in ENTRY_POINT_CANDIDATES

                    file_descriptors.append(
                        FileDescriptor(
                            relative_path=rel_file,
                            language=language,
                            size_bytes=file_size,
                            sha256_hash=file_hash,
                            is_entry_point=is_entry,
                        )
                    )

                    count += 1
                    if count >= self.max_files:
                        logger.warning(f"Reached max file scan limit of {self.max_files}")
                        return file_descriptors

                except Exception as e:
                    logger.debug(f"Error inspecting file {rel_file}: {e}")

        return file_descriptors

    def extract_dependencies(self) -> List[DependencyDescriptor]:
        """Extracts dependencies from package manifests (requirements.txt, package.json)."""
        deps: List[DependencyDescriptor] = []

        # 1. requirements.txt
        req_path = self.repo_root / "requirements.txt"
        if req_path.is_file():
            try:
                with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("-"):
                            # Parse name and version
                            parts = line.split(";")  # strip markers
                            dep_spec = parts[0].strip()
                            name = dep_spec.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                            if name:
                                deps.append(
                                    DependencyDescriptor(
                                        name=name,
                                        version_spec=dep_spec if dep_spec != name else None,
                                        ecosystem="python",
                                        is_dev=False,
                                    )
                                )
            except Exception as e:
                logger.warning(f"Error reading requirements.txt: {e}")

        # 2. package.json
        pkg_path = self.repo_root / "package.json"
        if pkg_path.is_file():
            try:
                with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                    pkg_data = json.load(f)
                    
                    prod_deps = pkg_data.get("dependencies", {})
                    for name, ver in prod_deps.items():
                        deps.append(
                            DependencyDescriptor(
                                name=name,
                                version_spec=str(ver),
                                ecosystem="npm",
                                is_dev=False,
                            )
                        )
                    
                    dev_deps = pkg_data.get("devDependencies", {})
                    for name, ver in dev_deps.items():
                        deps.append(
                            DependencyDescriptor(
                                name=name,
                                version_spec=str(ver),
                                ecosystem="npm",
                                is_dev=True,
                            )
                        )
            except Exception as e:
                logger.warning(f"Error reading package.json: {e}")

        return deps

    @staticmethod
    def _compute_hash(path: Path) -> str:
        """Computes SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _is_binary_file(path: Path) -> bool:
        """Checks if a file is binary by looking for null bytes in the header."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True
