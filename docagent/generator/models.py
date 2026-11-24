"""Data models for documentation generation, proposals, and evidence grounding."""

import difflib
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocType(str, Enum):
    README = "readme"
    ARCHITECTURE = "architecture"
    API_REFERENCE = "api_reference"
    CONFIGURATION = "configuration"
    CHANGELOG = "changelog"
    TROUBLESHOOTING = "troubleshooting"
    ONBOARDING = "onboarding"
    MODULES = "modules"


class EvidenceAnchor(BaseModel):
    """Grounding evidence pointing to source code or verified commit."""
    source_file: str
    symbol_name: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    commit_sha: Optional[str] = None
    confidence: float = 1.0
    rationale: Optional[str] = None


class DocProposal(BaseModel):
    """A proposed creation or modification of a documentation file."""
    file_path: str
    doc_type: DocType
    original_content: str = ""
    proposed_content: str = ""
    unified_diff: str = ""
    rationale: str = ""
    evidence_anchors: List[EvidenceAnchor] = Field(default_factory=list)
    is_new_file: bool = False
    uncertain_claims: List[str] = Field(default_factory=list)

    def compute_diff(self) -> str:
        """Computes unified diff between original_content and proposed_content."""
        orig_lines = self.original_content.splitlines(keepends=True)
        prop_lines = self.proposed_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            prop_lines,
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm=""
        )
        self.unified_diff = "".join(diff)
        return self.unified_diff
