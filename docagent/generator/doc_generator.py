"""Core documentation generator coordinating templates, LLM synthesis, and diff computation."""

from pathlib import Path
from typing import List, Optional

from docagent.analyzer.models import CodeInventory, GitChangeSet
from docagent.core.logging import logger
from docagent.generator.llm_client import BaseLLMClient, get_llm_client
from docagent.generator.models import DocProposal, DocType
from docagent.generator.templates import (
    render_api_reference,
    render_changelog,
    render_configuration_reference,
    render_modules_documentation,
    render_onboarding_guide,
    render_readme,
)
from docagent.security.path_validator import validate_contained_path


class DocGenerator:
    """Generates and updates documentation proposals grounded in code evidence."""

    def __init__(self, repo_root: Path, llm_client: Optional[BaseLLMClient] = None):
        self.repo_root = validate_contained_path(repo_root, repo_root)
        self.llm_client = llm_client or get_llm_client()

    def generate_readme(
        self,
        inventory: CodeInventory,
        summary_override: Optional[str] = None
    ) -> DocProposal:
        """Generates or updates README.md."""
        file_path = "README.md"
        full_path = self.repo_root / file_path
        
        orig_content = ""
        is_new = not full_path.is_file()
        if not is_new:
            try:
                orig_content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read existing {file_path}: {e}")

        # Render deterministic grounded template
        content, anchors = render_readme(inventory, summary_text=summary_override)

        proposal = DocProposal(
            file_path=file_path,
            doc_type=DocType.README,
            original_content=orig_content,
            proposed_content=content,
            is_new_file=is_new,
            rationale="Updated README.md grounded in verified code inventory and discovered entry points.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    def generate_api_reference(self, inventory: CodeInventory) -> DocProposal:
        """Generates or updates docs/api_reference.md."""
        file_path = "docs/api_reference.md"
        full_path = self.repo_root / file_path

        orig_content = ""
        is_new = not full_path.is_file()
        if not is_new:
            try:
                orig_content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read existing {file_path}: {e}")

        content, anchors = render_api_reference(inventory)

        proposal = DocProposal(
            file_path=file_path,
            doc_type=DocType.API_REFERENCE,
            original_content=orig_content,
            proposed_content=content,
            is_new_file=is_new,
            rationale="Generated API reference from static AST/Tree-sitter route definitions.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    def generate_configuration_reference(self, inventory: CodeInventory) -> DocProposal:
        """Generates or updates docs/configuration.md."""
        file_path = "docs/configuration.md"
        full_path = self.repo_root / file_path

        orig_content = ""
        is_new = not full_path.is_file()
        if not is_new:
            try:
                orig_content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read existing {file_path}: {e}")

        content, anchors = render_configuration_reference(inventory)

        proposal = DocProposal(
            file_path=file_path,
            doc_type=DocType.CONFIGURATION,
            original_content=orig_content,
            proposed_content=content,
            is_new_file=is_new,
            rationale="Documented environment variables and configuration keys detected in source code.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    def generate_changelog(self, change_set: GitChangeSet) -> DocProposal:
        """Generates or updates CHANGELOG.md from git change set."""
        file_path = "CHANGELOG.md"
        full_path = self.repo_root / file_path

        orig_content = ""
        is_new = not full_path.is_file()
        if not is_new:
            try:
                orig_content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read existing {file_path}: {e}")

        new_entries, anchors = render_changelog(change_set)

        # Prepend to existing changelog if already present
        if orig_content.strip():
            proposed = f"{new_entries}\n\n---\n\n{orig_content}"
        else:
            proposed = new_entries

        proposal = DocProposal(
            file_path=file_path,
            doc_type=DocType.CHANGELOG,
            original_content=orig_content,
            proposed_content=proposed,
            is_new_file=is_new,
            rationale="Recorded semantic git changes, breaking API modifications, and affected symbols.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    def generate_modules_reference(self, inventory: CodeInventory) -> DocProposal:
        """Generates docs/modules.md."""
        file_path = "docs/modules.md"
        full_path = self.repo_root / file_path
        orig_content = ""
        is_new = not full_path.is_file()
        if not is_new:
            try:
                orig_content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read existing {file_path}: {e}")

        content, anchors = render_modules_documentation(inventory)
        proposal = DocProposal(
            file_path=file_path,
            doc_type=DocType.MODULES,
            original_content=orig_content,
            proposed_content=content,
            is_new_file=is_new,
            rationale="Generated detailed module and package reference from AST symbols.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    def generate_onboarding_guide(self, inventory: CodeInventory) -> DocProposal:
        """Generates docs/onboarding.md."""
        file_path = "docs/onboarding.md"
        full_path = self.repo_root / file_path
        orig_content = ""
        is_new = not full_path.is_file()
        if not is_new:
            try:
                orig_content = full_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Could not read existing {file_path}: {e}")

        content, anchors = render_onboarding_guide(inventory)
        proposal = DocProposal(
            file_path=file_path,
            doc_type=DocType.ONBOARDING,
            original_content=orig_content,
            proposed_content=content,
            is_new_file=is_new,
            rationale="Generated onboarding guide with dependencies and configuration setup.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    def generate_all(
        self,
        inventory: CodeInventory,
        change_set: Optional[GitChangeSet] = None
    ) -> List[DocProposal]:
        """Generates complete documentation suite."""
        proposals: List[DocProposal] = [
            self.generate_readme(inventory),
            self.generate_configuration_reference(inventory),
            self.generate_modules_reference(inventory),
            self.generate_onboarding_guide(inventory),
        ]

        if inventory.api_routes:
            proposals.append(self.generate_api_reference(inventory))

        if change_set and change_set.files_changed:
            proposals.append(self.generate_changelog(change_set))

        return proposals
