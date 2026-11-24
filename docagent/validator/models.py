"""Data models for documentation claims, consistency checks, and drift detection."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    CRITICAL = "critical"  # Hallucinated or deleted API endpoint / missing mandatory symbol
    WARNING = "warning"    # Missing config var, obsolete dependency, parameter mismatch
    INFO = "info"          # Style or minor discrepancy


class ValidationRule(str, Enum):
    MISSING_SYMBOL = "missing_symbol"
    INCORRECT_API_ROUTE = "incorrect_api_route"
    OBSOLETE_DEPENDENCY = "obsolete_dependency"
    MISSING_CONFIG_KEY = "missing_config_key"
    OUTDATED_PARAMETER = "outdated_parameter"
    UNVERIFIED_CLAIM = "unverified_claim"


class ValidationFinding(BaseModel):
    """Specific discrepancy or hallucination identified in documentation."""
    rule: ValidationRule
    severity: FindingSeverity
    doc_file: str
    line_number: Optional[int] = None
    claim: str
    message: str
    evidence_path: Optional[str] = None
    suggested_fix: Optional[str] = None


class ValidationReport(BaseModel):
    """Aggregate result of documentation consistency verification."""
    total_findings: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    is_valid: bool = True
    findings: List[ValidationFinding] = Field(default_factory=list)

    def add_finding(self, finding: ValidationFinding) -> None:
        """Appends a finding and updates counters."""
        self.findings.append(finding)
        self.total_findings += 1
        if finding.severity == FindingSeverity.CRITICAL:
            self.critical_count += 1
            self.is_valid = False
        elif finding.severity == FindingSeverity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1
