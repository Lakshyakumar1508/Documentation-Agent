"""Data models representing code inventory, git changes, logs, and documentation."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SymbolKind(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    CONSTANT = "constant"
    VARIABLE = "variable"


class ParameterDescriptor(BaseModel):
    """Details for a single function or method argument."""
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    is_optional: bool = False
    description: Optional[str] = None


class SymbolDescriptor(BaseModel):
    """Extracted code symbol (Function, Class, Method, Interface)."""
    name: str
    qualified_name: str
    kind: SymbolKind
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    parameters: List[ParameterDescriptor] = Field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)
    is_exported: bool = True
    is_async: bool = False
    parent_class: Optional[str] = None


class APIRouteDescriptor(BaseModel):
    """API endpoint detected in source code (FastAPI, Flask, Express, etc.)."""
    http_method: str  # GET, POST, PUT, DELETE, PATCH
    path: str  # e.g., "/api/v1/users/{id}"
    handler_name: str
    file_path: str
    line_number: int
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    auth_required: bool = False


class ConfigDescriptor(BaseModel):
    """Configuration variable or environment variable detected in code/files."""
    key: str
    source_file: str
    default_value: Optional[str] = None
    description: Optional[str] = None
    is_secret: bool = False


class DependencyDescriptor(BaseModel):
    """External library or package dependency."""
    name: str
    version_spec: Optional[str] = None
    ecosystem: str  # "python", "npm", etc.
    is_dev: bool = False


class FileDescriptor(BaseModel):
    """Metadata for a scanned source file."""
    relative_path: str
    language: str
    size_bytes: int
    sha256_hash: str
    is_entry_point: bool = False
    imports: List[str] = Field(default_factory=list)
    exported_symbols: List[str] = Field(default_factory=list)


class CodeInventory(BaseModel):
    """Unified structural inventory of an entire repository."""
    repo_name: str
    repo_root: str
    scanned_at: str
    total_files: int = 0
    files: List[FileDescriptor] = Field(default_factory=list)
    symbols: List[SymbolDescriptor] = Field(default_factory=list)
    api_routes: List[APIRouteDescriptor] = Field(default_factory=list)
    configs: List[ConfigDescriptor] = Field(default_factory=list)
    dependencies: List[DependencyDescriptor] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)

    def get_symbol_by_name(self, name: str) -> Optional[SymbolDescriptor]:
        """Lookup a symbol by simple or qualified name."""
        for s in self.symbols:
            if s.name == name or s.qualified_name == name:
                return s
        return None

    def get_routes_for_path(self, path: str) -> List[APIRouteDescriptor]:
        """Find routes matching a given path."""
        return [r for r in self.api_routes if r.path == path]


# --- Git Change Models ---

class FileChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class DiffHunk(BaseModel):
    """Unified diff hunk."""
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    lines: List[str] = Field(default_factory=list)


class FileDiff(BaseModel):
    """Diff details for a single changed file."""
    file_path: str
    old_path: Optional[str] = None
    change_type: FileChangeType
    hunks: List[DiffHunk] = Field(default_factory=list)
    modified_line_numbers: List[int] = Field(default_factory=list)


class BreakingChangeSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class BreakingChange(BaseModel):
    """Detected breaking change in public API or configuration."""
    kind: str  # "symbol_removed", "parameter_added_without_default", "route_removed", "config_removed"
    symbol_name: str
    file_path: str
    description: str
    severity: BreakingChangeSeverity = BreakingChangeSeverity.CRITICAL


class GitChangeSet(BaseModel):
    """Comprehensive analysis of changes across git commits or working tree."""
    base_ref: Optional[str] = None
    head_ref: Optional[str] = None
    commit_sha: Optional[str] = None
    files_changed: List[FileDiff] = Field(default_factory=list)
    breaking_changes: List[BreakingChange] = Field(default_factory=list)
    affected_symbol_names: List[str] = Field(default_factory=list)
    affected_route_paths: List[str] = Field(default_factory=list)


# --- Log Analysis Models ---

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class LogEntry(BaseModel):
    """Structured representation of a parsed log record."""
    timestamp: Optional[str] = None
    level: LogLevel = LogLevel.INFO
    message: str
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    file_reference: Optional[str] = None
    line_number: Optional[int] = None
    trace_id: Optional[str] = None


class ErrorCluster(BaseModel):
    """Clustered group of repetitive errors sharing a normalized trace signature."""
    signature_hash: str
    error_type: str
    representative_message: str
    occurrences: int = 1
    sample_stack_trace: str
    affected_files: List[str] = Field(default_factory=list)


class LogAnalysisResult(BaseModel):
    """Aggregated output of log analysis across application and CI runs."""
    total_entries: int = 0
    error_count: int = 0
    warning_count: int = 0
    clusters: List[ErrorCluster] = Field(default_factory=list)
    observed_facts: List[str] = Field(default_factory=list)
    inferred_recommendations: List[str] = Field(default_factory=list)
