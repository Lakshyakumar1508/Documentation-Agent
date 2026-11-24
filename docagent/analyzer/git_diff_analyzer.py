"""Git change analyzer with unified diff parsing and breaking API change detection."""

import os
from pathlib import Path
import re
import subprocess
from typing import List, Optional, Set, Tuple

import git

from docagent.analyzer.models import (
    BreakingChange,
    BreakingChangeSeverity,
    CodeInventory,
    DiffHunk,
    FileChangeType,
    FileDiff,
    GitChangeSet,
)
from docagent.core.logging import logger
from docagent.security.path_validator import validate_contained_path


HUNK_HEADER_REGEX = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


class GitDiffAnalyzer:
    """Analyzes Git diffs, working tree changes, and breaking API modifications."""

    def __init__(self, repo_root: Path):
        self.repo_root = validate_contained_path(repo_root, repo_root)

    def is_git_repo(self) -> bool:
        """Determines if repo_root is inside a valid git repository."""
        try:
            repo = git.Repo(self.repo_root, search_parent_directories=True)
            repo.close()
            return True
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return False

    def get_working_tree_changes(self, current_inventory: Optional[CodeInventory] = None) -> GitChangeSet:
        """Analyzes uncommitted changes in the working tree against HEAD."""
        if not self.is_git_repo():
            logger.info("Not a git repository. Returning empty changeset.")
            return GitChangeSet()

        repo = None
        try:
            repo = git.Repo(self.repo_root, search_parent_directories=True)
            # Try git diff HEAD; if HEAD doesn't exist (fresh repo), use diff against empty tree
            try:
                raw_diff = repo.git.diff("HEAD")
            except git.GitCommandError:
                raw_diff = repo.git.diff()

            change_set = self.parse_unified_diff(raw_diff)
            change_set.head_ref = "WORKING_TREE"
            try:
                change_set.commit_sha = repo.head.commit.hexsha
                change_set.base_ref = repo.active_branch.name
            except Exception:
                change_set.base_ref = "HEAD"

            if current_inventory:
                self.correlate_with_inventory(change_set, current_inventory)

            return change_set
        except Exception as e:
            logger.warning(f"Failed to inspect working tree git diff: {e}")
            return GitChangeSet()
        finally:
            if repo is not None:
                repo.close()

    def get_commit_range_changes(
        self,
        base_ref: str,
        head_ref: str,
        old_inventory: Optional[CodeInventory] = None,
        new_inventory: Optional[CodeInventory] = None,
    ) -> GitChangeSet:
        """Analyzes changes between two Git commits or branches."""
        if not self.is_git_repo():
            return GitChangeSet()

        repo = None
        try:
            repo = git.Repo(self.repo_root, search_parent_directories=True)
            raw_diff = repo.git.diff(f"{base_ref}...{head_ref}")
            change_set = self.parse_unified_diff(raw_diff)
            change_set.base_ref = base_ref
            change_set.head_ref = head_ref

            if new_inventory:
                self.correlate_with_inventory(change_set, new_inventory)
            if old_inventory and new_inventory:
                self.detect_breaking_changes(change_set, old_inventory, new_inventory)

            return change_set
        except Exception as e:
            logger.warning(f"Failed to inspect git diff between {base_ref} and {head_ref}: {e}")
            return GitChangeSet()
        finally:
            if repo is not None:
                repo.close()

    @classmethod
    def parse_unified_diff(cls, diff_text: str) -> GitChangeSet:
        """Parses unified diff format text into structured FileDiff and DiffHunk objects."""
        change_set = GitChangeSet()
        if not diff_text or not diff_text.strip():
            return change_set

        current_file_diff: Optional[FileDiff] = None
        current_hunk: Optional[DiffHunk] = None
        current_new_line_idx = 0

        lines = diff_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect git diff header: diff --git a/path b/path
            if line.startswith("diff --git "):
                if current_file_diff:
                    if current_hunk:
                        current_file_diff.hunks.append(current_hunk)
                        current_hunk = None
                    change_set.files_changed.append(current_file_diff)

                parts = line.split(" ")
                old_p = parts[2].lstrip("a/") if len(parts) > 2 else ""
                new_p = parts[3].lstrip("b/") if len(parts) > 3 else ""

                current_file_diff = FileDiff(
                    file_path=new_p,
                    old_path=old_p if old_p != new_p else None,
                    change_type=FileChangeType.MODIFIED,
                )
                i += 1
                continue

            # Detect new/deleted file mode
            if current_file_diff:
                if line.startswith("new file mode"):
                    current_file_diff.change_type = FileChangeType.ADDED
                elif line.startswith("deleted file mode"):
                    current_file_diff.change_type = FileChangeType.DELETED
                elif line.startswith("rename from"):
                    current_file_diff.change_type = FileChangeType.RENAMED
                elif line.startswith("--- "):
                    if line.startswith("--- /dev/null"):
                        current_file_diff.change_type = FileChangeType.ADDED
                elif line.startswith("+++ "):
                    if line.startswith("+++ /dev/null"):
                        current_file_diff.change_type = FileChangeType.DELETED

            # Detect Hunk header: @@ -1,5 +1,6 @@
            hunk_match = HUNK_HEADER_REGEX.match(line)
            if hunk_match and current_file_diff:
                if current_hunk:
                    current_file_diff.hunks.append(current_hunk)

                old_start = int(hunk_match.group(1))
                old_lines = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_lines = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                header_extra = hunk_match.group(5)

                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_lines=old_lines,
                    new_start=new_start,
                    new_lines=new_lines,
                    header=header_extra.strip(),
                )
                current_new_line_idx = new_start
                i += 1
                continue

            # Inside a hunk
            if current_hunk and current_file_diff:
                current_hunk.lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    current_file_diff.modified_line_numbers.append(current_new_line_idx)
                    current_new_line_idx += 1
                elif line.startswith("-") and not line.startswith("---"):
                    pass  # Deleted line in old version
                else:
                    # Context line
                    current_new_line_idx += 1

            i += 1

        # Wrap up trailing elements
        if current_file_diff:
            if current_hunk:
                current_file_diff.hunks.append(current_hunk)
            change_set.files_changed.append(current_file_diff)

        return change_set

    @classmethod
    def correlate_with_inventory(cls, change_set: GitChangeSet, inventory: CodeInventory) -> None:
        """Associates modified lines in changed files with symbols and routes in the inventory."""
        affected_symbols: Set[str] = set()
        affected_routes: Set[str] = set()

        for f_diff in change_set.files_changed:
            target_path = f_diff.file_path.replace("\\", "/")
            mod_lines = set(f_diff.modified_line_numbers)

            # Match against symbols
            for sym in inventory.symbols:
                sym_path = sym.file_path.replace("\\", "/")
                if sym_path == target_path:
                    # Check line range overlap
                    sym_range = range(sym.start_line, sym.end_line + 1)
                    if any(line in sym_range for line in mod_lines):
                        affected_symbols.add(sym.qualified_name)

            # Match against routes
            for route in inventory.api_routes:
                route_path = route.file_path.replace("\\", "/")
                if route_path == target_path:
                    if route.line_number in mod_lines:
                        affected_routes.add(f"{route.http_method} {route.path}")

        change_set.affected_symbol_names = sorted(list(affected_symbols))
        change_set.affected_route_paths = sorted(list(affected_routes))

    @classmethod
    def detect_breaking_changes(
        cls,
        change_set: GitChangeSet,
        old_inv: CodeInventory,
        new_inv: CodeInventory
    ) -> List[BreakingChange]:
        """Compares old and new code inventories to identify breaking API changes."""
        breaking: List[BreakingChange] = []

        old_symbols_map = {s.qualified_name: s for s in old_inv.symbols if s.is_exported}
        new_symbols_map = {s.qualified_name: s for s in new_inv.symbols if s.is_exported}

        # 1. Removed Symbols
        for name, old_s in old_symbols_map.items():
            if name not in new_symbols_map:
                breaking.append(
                    BreakingChange(
                        kind="symbol_removed",
                        symbol_name=name,
                        file_path=old_s.file_path,
                        description=f"Exported {old_s.kind.value} '{name}' was removed.",
                        severity=BreakingChangeSeverity.CRITICAL,
                    )
                )

        # 2. Altered Signatures: parameter added without default value
        for name, new_s in new_symbols_map.items():
            if name in old_symbols_map:
                old_s = old_symbols_map[name]
                old_param_names = {p.name for p in old_s.parameters}
                
                for p in new_s.parameters:
                    if p.name not in old_param_names and not p.is_optional and p.default_value is None:
                        breaking.append(
                            BreakingChange(
                                kind="parameter_added_without_default",
                                symbol_name=name,
                                file_path=new_s.file_path,
                                description=(
                                    f"Required parameter '{p.name}' was added to '{name}' without a default value."
                                ),
                                severity=BreakingChangeSeverity.CRITICAL,
                            )
                        )

        # 3. Removed API Routes
        new_route_keys = {(r.http_method, r.path) for r in new_inv.api_routes}
        for old_r in old_inv.api_routes:
            if (old_r.http_method, old_r.path) not in new_route_keys:
                breaking.append(
                    BreakingChange(
                        kind="route_removed",
                        symbol_name=f"{old_r.http_method} {old_r.path}",
                        file_path=old_r.file_path,
                        description=f"API Route '{old_r.http_method} {old_r.path}' was removed.",
                        severity=BreakingChangeSeverity.CRITICAL,
                    )
                )

        # 4. Removed Configs
        new_cfg_keys = {c.key for c in new_inv.configs}
        for old_c in old_inv.configs:
            if old_c.key not in new_cfg_keys:
                breaking.append(
                    BreakingChange(
                        kind="config_removed",
                        symbol_name=old_c.key,
                        file_path=old_c.source_file,
                        description=f"Configuration / Environment key '{old_c.key}' was removed.",
                        severity=BreakingChangeSeverity.WARNING,
                    )
                )

        change_set.breaking_changes = breaking
        return breaking
