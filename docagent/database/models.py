"""SQLAlchemy ORM models for jobs, changes, validation, and history."""

from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    full_name = Column(String(255), unique=True, nullable=False, index=True)
    default_branch = Column(String(100), default="main")
    local_path = Column(String(1024), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    jobs = relationship("AnalysisJob", back_populates="repository", cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    repository_id = Column(String(36), ForeignKey("repositories.id"), nullable=True, index=True)
    trigger_source = Column(String(50), nullable=False)  # "cli", "vscode", "github_webhook"
    commit_sha = Column(String(40), nullable=True, index=True)
    target_branch = Column(String(100), nullable=True)
    status = Column(String(50), default="PENDING", index=True)  # PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    repository = relationship("Repository", back_populates="jobs")
    changes = relationship("DocumentationChangeRecord", back_populates="job", cascade="all, delete-orphan")
    findings = relationship("ValidationFindingRecord", back_populates="job", cascade="all, delete-orphan")


class DocumentationChangeRecord(Base):
    __tablename__ = "documentation_changes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    doc_type = Column(String(50), nullable=False)
    unified_diff = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    is_applied = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    job = relationship("AnalysisJob", back_populates="changes")


class ValidationFindingRecord(Base):
    __tablename__ = "validation_findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id"), nullable=False, index=True)
    rule_name = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # CRITICAL, WARNING, INFO
    target_file = Column(String(512), nullable=False)
    line_number = Column(Integer, nullable=True)
    claim = Column(String(1024), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    job = relationship("AnalysisJob", back_populates="findings")
