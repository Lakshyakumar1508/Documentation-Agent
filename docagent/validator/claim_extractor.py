"""Extracts verifiable claims from Markdown documentation."""

import re
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class ExtractedClaim(BaseModel):
    """An individual assertion parsed from markdown text."""
    claim_type: str  # "route", "config", "dependency", "symbol"
    value: str
    line_number: int
    raw_context: str


# Regex matchers for claims
HTTP_ROUTE_REGEX = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+([/][a-zA-Z0-9_\-\./{}]+)",
    re.IGNORECASE
)
ENV_VAR_REGEX = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\b")
PIP_INSTALL_REGEX = re.compile(r"(?:pip|pip3)\s+install\s+([a-zA-Z0-9_\-\.]+)")
NPM_INSTALL_REGEX = re.compile(r"(?:npm\s+i(?:nstall)?|pnpm\s+add|yarn\s+add)\s+([a-zA-Z0-9_\-@\./]+)")
BACKTICK_SYMBOL_REGEX = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_]{2,})`")

COMMON_NON_ENV_WORDS = {
    "HTTP", "HTTPS", "JSON", "HTML", "REST", "CRUD", "CORS", "UUID",
    "POST", "GET", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRUE",
    "FALSE", "NULL", "NONE", "INFO", "WARN", "ERROR", "TODO", "NOTE"
}


class ClaimExtractor:
    """Scans markdown lines and extracts verifiable structural claims."""

    @classmethod
    def extract_claims(cls, markdown_text: str) -> List[ExtractedClaim]:
        claims: List[ExtractedClaim] = []
        lines = markdown_text.splitlines()

        in_code_block = False

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Track fenced code blocks
            if stripped.startswith("```"):
                in_code_block = not in_code_block

            # Skip JSON example error response lines or mock validation claims
            if stripped.startswith(('"claim":', '"message":', '"error":', '"suggested_fix":')):
                continue

            # 1. HTTP Routes: e.g. `GET /api/v1/orders`
            for match in HTTP_ROUTE_REGEX.finditer(line):
                method = match.group(1).upper()
                path = match.group(2)
                claims.append(
                    ExtractedClaim(
                        claim_type="route",
                        value=f"{method} {path}",
                        line_number=idx,
                        raw_context=line.strip(),
                    )
                )

            # 2. Dependency commands: pip install fastapi, npm install express
            for match in PIP_INSTALL_REGEX.finditer(line):
                pkg_name = match.group(1).split("==")[0].split(">=")[0].split("<=")[0]
                if pkg_name.startswith("-") or pkg_name in (".", "..") or pkg_name.endswith(".txt"):
                    continue
                claims.append(
                    ExtractedClaim(
                        claim_type="dependency",
                        value=pkg_name,
                        line_number=idx,
                        raw_context=line.strip(),
                    )
                )

            for match in NPM_INSTALL_REGEX.finditer(line):
                pkg_name = match.group(1)
                claims.append(
                    ExtractedClaim(
                        claim_type="dependency",
                        value=pkg_name,
                        line_number=idx,
                        raw_context=line.strip(),
                    )
                )

            # 3. Environment Variables: e.g. DATABASE_URL
            for match in ENV_VAR_REGEX.finditer(line):
                var_name = match.group(1)
                if var_name not in COMMON_NON_ENV_WORDS and "_" in var_name:
                    claims.append(
                        ExtractedClaim(
                            claim_type="config",
                            value=var_name,
                            line_number=idx,
                            raw_context=line.strip(),
                        )
                    )

            # 4. Code Symbols in backticks: `process_order`
            for match in BACKTICK_SYMBOL_REGEX.finditer(line):
                sym_name = match.group(1)
                # Ignore common markdown or format keywords
                if sym_name not in ("true", "false", "null", "none", "str", "int", "bool", "dict", "list"):
                    claims.append(
                        ExtractedClaim(
                            claim_type="symbol",
                            value=sym_name,
                            line_number=idx,
                            raw_context=line.strip(),
                        )
                    )

        return claims
