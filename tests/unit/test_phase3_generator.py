"""Unit tests for Phase 3: Documentation Generator Engine."""

from pathlib import Path
import pytest

from docagent.analyzer.models import (
    APIRouteDescriptor,
    BreakingChange,
    BreakingChangeSeverity,
    CodeInventory,
    ConfigDescriptor,
    DependencyDescriptor,
    FileChangeType,
    FileDescriptor,
    FileDiff,
    GitChangeSet,
    SymbolDescriptor,
    SymbolKind,
)
from docagent.generator.doc_generator import DocGenerator
from docagent.generator.llm_client import MockLLMClient, OpenAICompatibleClient, get_llm_client
from docagent.generator.models import DocType


@pytest.fixture
def sample_inventory():
    return CodeInventory(
        repo_name="OrderService",
        repo_root="/workspace/order_service",
        scanned_at="2026-11-24T10:00:00Z",
        total_files=2,
        files=[
            FileDescriptor(
                relative_path="src/main.py",
                language="python",
                size_bytes=500,
                sha256_hash="abc123hash",
                is_entry_point=True,
                exported_symbols=["app", "create_order"],
            ),
            FileDescriptor(
                relative_path="src/config.py",
                language="python",
                size_bytes=200,
                sha256_hash="def456hash",
                is_entry_point=False,
                exported_symbols=["Settings"],
            ),
        ],
        symbols=[
            SymbolDescriptor(
                name="create_order",
                qualified_name="create_order",
                kind=SymbolKind.FUNCTION,
                file_path="src/main.py",
                start_line=10,
                end_line=20,
            )
        ],
        api_routes=[
            APIRouteDescriptor(
                http_method="POST",
                path="/api/v1/orders",
                handler_name="create_order",
                file_path="src/main.py",
                line_number=10,
                auth_required=True,
            )
        ],
        configs=[
            ConfigDescriptor(
                key="DATABASE_URL",
                source_file="src/config.py",
                default_value="sqlite:///orders.db",
                is_secret=False,
            ),
            ConfigDescriptor(
                key="STRIPE_SECRET_KEY",
                source_file="src/config.py",
                default_value=None,
                is_secret=True,
            ),
        ],
        dependencies=[
            DependencyDescriptor(
                name="fastapi",
                version_spec=">=0.110.0",
                ecosystem="python",
            )
        ],
        entry_points=["src/main.py"],
    )


def test_generate_readme(tmp_path, sample_inventory):
    gen = DocGenerator(tmp_path)
    proposal = gen.generate_readme(sample_inventory)

    assert proposal.doc_type == DocType.README
    assert proposal.file_path == "README.md"
    assert proposal.is_new_file is True
    assert "# OrderService" in proposal.proposed_content
    assert "`src/main.py`" in proposal.proposed_content
    assert "DATABASE_URL" in proposal.proposed_content
    assert "/api/v1/orders" in proposal.proposed_content
    assert len(proposal.evidence_anchors) > 0


def test_generate_api_reference(tmp_path, sample_inventory):
    gen = DocGenerator(tmp_path)
    proposal = gen.generate_api_reference(sample_inventory)

    assert proposal.doc_type == DocType.API_REFERENCE
    assert proposal.file_path == "docs/api_reference.md"
    assert "### `POST /api/v1/orders`" in proposal.proposed_content
    assert "create_order" in proposal.proposed_content
    assert "Required" in proposal.proposed_content


def test_generate_configuration_reference(tmp_path, sample_inventory):
    gen = DocGenerator(tmp_path)
    proposal = gen.generate_configuration_reference(sample_inventory)

    assert proposal.doc_type == DocType.CONFIGURATION
    assert proposal.file_path == "docs/configuration.md"
    assert "DATABASE_URL" in proposal.proposed_content
    assert "STRIPE_SECRET_KEY" in proposal.proposed_content
    assert "Yes" in proposal.proposed_content  # Sensitive flag for Stripe key


def test_generate_changelog_with_breaking(tmp_path):
    change_set = GitChangeSet(
        base_ref="v1.0.0",
        head_ref="v2.0.0",
        files_changed=[
            FileDiff(
                file_path="src/main.py",
                change_type=FileChangeType.MODIFIED,
            )
        ],
        breaking_changes=[
            BreakingChange(
                kind="route_removed",
                symbol_name="DELETE /api/v1/orders/{id}",
                file_path="src/main.py",
                description="Endpoint was decommissioned.",
                severity=BreakingChangeSeverity.CRITICAL,
            )
        ],
        affected_symbol_names=["create_order"],
    )

    gen = DocGenerator(tmp_path)
    proposal = gen.generate_changelog(change_set)

    assert proposal.doc_type == DocType.CHANGELOG
    assert "⚠️ Breaking Changes" in proposal.proposed_content
    assert "DELETE /api/v1/orders/{id}" in proposal.proposed_content
    assert "Endpoint was decommissioned." in proposal.proposed_content


def test_diff_computation_on_existing_file(tmp_path, sample_inventory):
    # Pre-create existing README
    readme_file = tmp_path / "README.md"
    readme_file.write_text("# Old Title\nSome old docs.", encoding="utf-8")

    gen = DocGenerator(tmp_path)
    proposal = gen.generate_readme(sample_inventory)

    assert proposal.is_new_file is False
    assert "-# Old Title" in proposal.unified_diff
    assert "+# OrderService" in proposal.unified_diff


def test_mock_llm_client():
    client = MockLLMClient()
    res = client.generate("System", "User")
    assert "evidence-grounded" in res
