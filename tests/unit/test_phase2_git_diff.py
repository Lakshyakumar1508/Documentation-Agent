"""Unit tests for Phase 2: Git Diff Parsing and Breaking API Change Detection."""

from pathlib import Path
import git
import pytest

from docagent.analyzer.git_diff_analyzer import GitDiffAnalyzer
from docagent.analyzer.models import (
    APIRouteDescriptor,
    BreakingChangeSeverity,
    CodeInventory,
    ConfigDescriptor,
    FileChangeType,
    ParameterDescriptor,
    SymbolDescriptor,
    SymbolKind,
)


SAMPLE_DIFF = """diff --git a/src/app.py b/src/app.py
index 1234567..89abcdef 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,6 +10,8 @@ def existing_func():
     pass
 
+def new_feature(x: int):
+    return x * 2
+
 def another_func():
     return 1
diff --git a/docs/old.md b/docs/old.md
deleted file mode 100644
--- a/docs/old.md
+++ /dev/null
@@ -1,3 +0,0 @@
-# Old Doc
-Some old content.
"""


def test_parse_unified_diff():
    change_set = GitDiffAnalyzer.parse_unified_diff(SAMPLE_DIFF)
    assert len(change_set.files_changed) == 2

    # First file: modified app.py
    f1 = change_set.files_changed[0]
    assert f1.file_path == "src/app.py"
    assert f1.change_type == FileChangeType.MODIFIED
    assert len(f1.hunks) == 1
    assert 13 in f1.modified_line_numbers
    assert 14 in f1.modified_line_numbers

    # Second file: deleted old.md
    f2 = change_set.files_changed[1]
    assert f2.file_path == "docs/old.md"
    assert f2.change_type == FileChangeType.DELETED


def test_correlate_diff_with_inventory():
    change_set = GitDiffAnalyzer.parse_unified_diff(SAMPLE_DIFF)

    inv = CodeInventory(
        repo_name="sample",
        repo_root="/sample",
        scanned_at="2026-11-24T00:00:00Z",
        symbols=[
            SymbolDescriptor(
                name="new_feature",
                qualified_name="new_feature",
                kind=SymbolKind.FUNCTION,
                file_path="src/app.py",
                start_line=13,
                end_line=14,
            ),
            SymbolDescriptor(
                name="another_func",
                qualified_name="another_func",
                kind=SymbolKind.FUNCTION,
                file_path="src/app.py",
                start_line=16,
                end_line=17,
            ),
        ],
    )

    GitDiffAnalyzer.correlate_with_inventory(change_set, inv)
    assert "new_feature" in change_set.affected_symbol_names
    assert "another_func" not in change_set.affected_symbol_names


def test_breaking_change_detection():
    old_inv = CodeInventory(
        repo_name="sample",
        repo_root="/sample",
        scanned_at="2026-11-24T00:00:00Z",
        symbols=[
            SymbolDescriptor(
                name="process_order",
                qualified_name="process_order",
                kind=SymbolKind.FUNCTION,
                file_path="src/order.py",
                start_line=1,
                end_line=5,
                parameters=[ParameterDescriptor(name="order_id", type_annotation="str")],
            ),
            SymbolDescriptor(
                name="legacy_endpoint",
                qualified_name="legacy_endpoint",
                kind=SymbolKind.FUNCTION,
                file_path="src/legacy.py",
                start_line=1,
                end_line=5,
            ),
        ],
        api_routes=[
            APIRouteDescriptor(
                http_method="DELETE",
                path="/api/v1/orders/{id}",
                handler_name="delete_order",
                file_path="src/order.py",
                line_number=10,
            )
        ],
        configs=[
            ConfigDescriptor(key="LEGACY_API_KEY", source_file="src/config.py")
        ],
    )

    new_inv = CodeInventory(
        repo_name="sample",
        repo_root="/sample",
        scanned_at="2026-11-24T00:05:00Z",
        symbols=[
            # process_order added a mandatory parameter without default
            SymbolDescriptor(
                name="process_order",
                qualified_name="process_order",
                kind=SymbolKind.FUNCTION,
                file_path="src/order.py",
                start_line=1,
                end_line=5,
                parameters=[
                    ParameterDescriptor(name="order_id", type_annotation="str"),
                    ParameterDescriptor(name="auth_token", type_annotation="str", is_optional=False),
                ],
            ),
            # legacy_endpoint was completely removed
        ],
        api_routes=[],  # DELETE route removed
        configs=[],     # LEGACY_API_KEY removed
    )

    change_set = GitDiffAnalyzer.parse_unified_diff(SAMPLE_DIFF)
    breaking = GitDiffAnalyzer.detect_breaking_changes(change_set, old_inv, new_inv)

    kinds = [b.kind for b in breaking]
    assert "symbol_removed" in kinds
    assert "parameter_added_without_default" in kinds
    assert "route_removed" in kinds
    assert "config_removed" in kinds


def test_git_repo_live_diff(tmp_path):
    # Initialize a test git repo
    repo = git.Repo.init(tmp_path)
    try:
        # Configure user
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")

        # Initial commit
        file1 = tmp_path / "hello.py"
        file1.write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
        repo.index.add([str(file1)])
        repo.index.commit("Initial commit")

        analyzer = GitDiffAnalyzer(tmp_path)
        assert analyzer.is_git_repo() is True

        # Modify file without committing
        file1.write_text("def hello():\n    return 'hello world'\n", encoding="utf-8")
        
        change_set = analyzer.get_working_tree_changes()
        assert len(change_set.files_changed) == 1
        assert change_set.files_changed[0].file_path == "hello.py"
        assert change_set.files_changed[0].change_type == FileChangeType.MODIFIED
    finally:
        repo.close()
