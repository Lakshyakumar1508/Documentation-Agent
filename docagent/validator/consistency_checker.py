"""Documentation-to-code consistency verifier and drift detector."""

from pathlib import Path
from typing import List, Optional

from docagent.analyzer.models import CodeInventory
from docagent.core.logging import logger
from docagent.validator.claim_extractor import ClaimExtractor
from docagent.validator.models import (
    FindingSeverity,
    ValidationFinding,
    ValidationReport,
    ValidationRule,
)


class ConsistencyChecker:
    """Validates markdown documentation assertions against the active CodeInventory."""

    @classmethod
    def validate_document(
        cls,
        doc_path: str,
        doc_content: str,
        inventory: CodeInventory
    ) -> ValidationReport:
        """Compares claims in a single document against verified code inventory."""
        report = ValidationReport()
        claims = ClaimExtractor.extract_claims(doc_content)

        # Build fast lookup sets from inventory
        valid_routes = {(r.http_method.upper(), r.path) for r in inventory.api_routes}
        valid_configs = {c.key for c in inventory.configs}
        valid_deps = {d.name.lower() for d in inventory.dependencies}
        valid_symbols = {s.name for s in inventory.symbols} | {s.qualified_name for s in inventory.symbols}

        for claim in claims:
            # 1. Validate API Routes
            if claim.claim_type == "route":
                parts = claim.value.split(" ", 1)
                method, path = parts[0].upper(), parts[1]
                c_path = path.rstrip("/")

                matched = False
                for r in inventory.api_routes:
                    if r.http_method.upper() != method:
                        continue
                    r_path = r.path.rstrip("/")
                    # Exact match
                    if c_path == r_path:
                        matched = True
                        break
                    # Suffix match or stripped /api/v1 match
                    if r_path and (c_path.endswith(r_path) or c_path.replace("/api/v1", "").rstrip("/") == r_path):
                        matched = True
                        break
                    # Root route mounted under resource (e.g. /api/v1/jobs -> jobs router with "")
                    if not r_path and any(c_path.endswith(res) or c_path.endswith(f"{res}/") for res in ("/jobs", "/webhooks")):
                        matched = True
                        break

                if not matched:
                    report.add_finding(
                        ValidationFinding(
                            rule=ValidationRule.INCORRECT_API_ROUTE,
                            severity=FindingSeverity.CRITICAL,
                            doc_file=doc_path,
                            line_number=claim.line_number,
                            claim=claim.value,
                            message=f"Documented route '{claim.value}' does not exist in active code.",
                            suggested_fix="Verify route path and HTTP method in router definitions.",
                        )
                    )

            # 2. Validate Environment / Config Keys
            elif claim.claim_type == "config":
                if claim.value not in valid_configs:
                    report.add_finding(
                        ValidationFinding(
                            rule=ValidationRule.MISSING_CONFIG_KEY,
                            severity=FindingSeverity.WARNING,
                            doc_file=doc_path,
                            line_number=claim.line_number,
                            claim=claim.value,
                            message=f"Documented config variable '{claim.value}' was not found in codebase.",
                            suggested_fix=f"Check if '{claim.value}' is obsolete or declared externally.",
                        )
                    )

            # 3. Validate Dependencies
            elif claim.claim_type == "dependency":
                dep_name = claim.value.lower()
                # Exclude runtime tools (e.g. node, python, pip, npm)
                if dep_name not in ("node", "python", "pip", "npm", "pnpm", "yarn"):
                    if dep_name not in valid_deps:
                        report.add_finding(
                            ValidationFinding(
                                rule=ValidationRule.OBSOLETE_DEPENDENCY,
                                severity=FindingSeverity.WARNING,
                                doc_file=doc_path,
                                line_number=claim.line_number,
                                claim=claim.value,
                                message=f"Documented package '{claim.value}' is missing from package manifests.",
                                suggested_fix="Ensure dependency is listed in requirements.txt or package.json.",
                            )
                        )

            # 4. Validate Backticked Symbols (if context indicates function/method call)
            elif claim.claim_type == "symbol":
                # Only check symbols in lines that look like function declarations or descriptions
                ctx = claim.raw_context.lower()
                if any(kw in ctx for kw in ("function", "method", "class", "handler", "call", "returns", "implements")):
                    if claim.value not in valid_symbols:
                        report.add_finding(
                            ValidationFinding(
                                rule=ValidationRule.MISSING_SYMBOL,
                                severity=FindingSeverity.WARNING,
                                doc_file=doc_path,
                                line_number=claim.line_number,
                                claim=claim.value,
                                message=f"Documented symbol '{claim.value}' was not found in code AST.",
                                suggested_fix="Verify if the symbol was renamed, moved, or deleted.",
                            )
                        )

        return report

    @classmethod
    def validate_repository_docs(
        cls,
        repo_root: Path,
        inventory: CodeInventory
    ) -> ValidationReport:
        """Scans all markdown files in the repository and aggregates validation findings."""
        aggregated_report = ValidationReport()

        for f_desc in inventory.files:
            if f_desc.language == "markdown":
                full_path = repo_root / f_desc.relative_path
                try:
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    doc_report = cls.validate_document(f_desc.relative_path, content, inventory)
                    for finding in doc_report.findings:
                        aggregated_report.add_finding(finding)
                except Exception as e:
                    logger.warning(f"Error validating {f_desc.relative_path}: {e}")

        return aggregated_report
