"""Unit tests for Phase 4: Evidence Validation & Documentation Drift Detection."""

from pathlib import Path
import pytest

from docagent.analyzer.models import (
    APIRouteDescriptor,
    CodeInventory,
    ConfigDescriptor,
    DependencyDescriptor,
    FileDescriptor,
    SymbolDescriptor,
    SymbolKind,
)
from docagent.validator.claim_extractor import ClaimExtractor
from docagent.validator.consistency_checker import ConsistencyChecker
from docagent.validator.models import FindingSeverity, ValidationRule


@pytest.fixture
def test_inventory():
    return CodeInventory(
        repo_name="BillingService",
        repo_root="/workspace/billing",
        scanned_at="2026-11-24T10:00:00Z",
        total_files=2,
        symbols=[
            SymbolDescriptor(
                name="charge_card",
                qualified_name="charge_card",
                kind=SymbolKind.FUNCTION,
                file_path="src/billing.py",
                start_line=1,
                end_line=10,
            )
        ],
        api_routes=[
            APIRouteDescriptor(
                http_method="POST",
                path="/api/v1/charge",
                handler_name="charge_card",
                file_path="src/billing.py",
                line_number=1,
            )
        ],
        configs=[
            ConfigDescriptor(key="PAYMENT_GATEWAY_URL", source_file="src/config.py"),
            ConfigDescriptor(key="STRIPE_KEY", source_file="src/config.py"),
        ],
        dependencies=[
            DependencyDescriptor(name="fastapi", ecosystem="python"),
            DependencyDescriptor(name="stripe", ecosystem="python"),
        ],
    )


def test_claim_extractor():
    doc = """
# Quickstart
Install via `pip install stripe`.
Run `GET /api/v1/users` or `POST /api/v1/charge`.
Configure `PAYMENT_GATEWAY_URL` and `UNKNOWN_SECRET_TOKEN`.
Call function `charge_card` to execute.
"""
    claims = ClaimExtractor.extract_claims(doc)
    types = [c.claim_type for c in claims]
    vals = [c.value for c in claims]

    assert "route" in types
    assert "dependency" in types
    assert "config" in types
    assert "symbol" in types

    assert "POST /api/v1/charge" in vals
    assert "GET /api/v1/users" in vals
    assert "stripe" in vals
    assert "PAYMENT_GATEWAY_URL" in vals
    assert "UNKNOWN_SECRET_TOKEN" in vals


def test_validator_detects_hallucinated_route(test_inventory):
    doc = """
### API Reference
Use `GET /api/v1/nonexistent` to fetch accounts.
"""
    report = ConsistencyChecker.validate_document("README.md", doc, test_inventory)

    assert report.is_valid is False
    assert report.critical_count == 1
    finding = report.findings[0]
    assert finding.rule == ValidationRule.INCORRECT_API_ROUTE
    assert finding.severity == FindingSeverity.CRITICAL
    assert "GET /api/v1/nonexistent" in finding.claim


def test_validator_detects_missing_config(test_inventory):
    doc = """
Set environment variable `MISSING_DATABASE_URI` before starting.
"""
    report = ConsistencyChecker.validate_document("README.md", doc, test_inventory)

    assert report.warning_count >= 1
    finding = next(f for f in report.findings if f.rule == ValidationRule.MISSING_CONFIG_KEY)
    assert finding.claim == "MISSING_DATABASE_URI"


def test_validator_detects_obsolete_dependency(test_inventory):
    doc = """
```bash
pip install old_unregistered_package
```
"""
    report = ConsistencyChecker.validate_document("README.md", doc, test_inventory)

    assert report.warning_count >= 1
    finding = next(f for f in report.findings if f.rule == ValidationRule.OBSOLETE_DEPENDENCY)
    assert finding.claim == "old_unregistered_package"


def test_validator_detects_missing_symbol(test_inventory):
    doc = """
Call function `non_existent_function` to process payments.
"""
    report = ConsistencyChecker.validate_document("docs/guide.md", doc, test_inventory)

    assert report.warning_count >= 1
    finding = next(f for f in report.findings if f.rule == ValidationRule.MISSING_SYMBOL)
    assert finding.claim == "non_existent_function"


def test_validator_passes_on_grounded_doc(test_inventory):
    doc = """
# Billing Service
To install:
`pip install stripe`

Call handler `charge_card` via `POST /api/v1/charge`.
Configure `PAYMENT_GATEWAY_URL`.
"""
    report = ConsistencyChecker.validate_document("README.md", doc, test_inventory)

    # Should have 0 critical and 0 warning findings
    assert report.is_valid is True
    assert report.critical_count == 0
    assert report.warning_count == 0
