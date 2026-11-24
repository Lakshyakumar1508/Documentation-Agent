"""Multi-source log analyzer parsing Python, JS/TS, and CI logs with error clustering."""

import hashlib
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from docagent.analyzer.models import (
    ErrorCluster,
    LogAnalysisResult,
    LogEntry,
    LogLevel,
)
from docagent.core.logging import logger
from docagent.generator.models import DocProposal, DocType, EvidenceAnchor
from docagent.security.path_validator import validate_contained_path
from docagent.security.redaction import RedactionEngine


PYTHON_TRACEBACK_START = re.compile(r"^Traceback \(most recent call last\):")
PYTHON_FRAME_REGEX = re.compile(r'^\s*File "([^"]+)", line (\d+), in (.*)$')
PYTHON_EXCEPTION_REGEX = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_\.]*(?:Error|Exception|Warning|Fault)): (.*)$")

JS_STACK_START = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*(?:Error|Exception)): (.*)$")
JS_FRAME_REGEX = re.compile(r"^\s*at (?:(.+?)\s+\()?([^:()]+):(\d+):(\d+)\)?$")

TIMESTAMPED_LINE_REGEX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)\s*(?:\[(\w+)\]|\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\b)\s*(.*)$",
    re.IGNORECASE
)
TRACE_ID_REGEX = re.compile(r"(?i)\b(?:trace_id|request_id|correlation_id|req_id)[=:]\s*['\"]?([a-zA-Z0-9_\-]+)")


class LogAnalyzer:
    """Parses application and CI logs, groups repetitive failures, and drafts troubleshooting docs."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root:
            self.repo_root = validate_contained_path(repo_root, repo_root)
        else:
            self.repo_root = None

    def analyze_log_content(self, raw_log_text: str) -> LogAnalysisResult:
        """Sanitizes, parses, and clusters logs from string input."""
        # Step 1: Strict secret redaction
        clean_text = RedactionEngine.redact_text(raw_log_text)
        lines = clean_text.splitlines()

        entries: List[LogEntry] = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # 1. Check for Python Traceback
            if PYTHON_TRACEBACK_START.match(line):
                entry, next_i = self._parse_python_traceback(lines, i)
                entries.append(entry)
                i = next_i
                continue

            # 2. Check for JavaScript Unhandled Error
            js_match = JS_STACK_START.match(line)
            if js_match and i + 1 < len(lines) and "    at " in lines[i + 1]:
                entry, next_i = self._parse_js_stack(lines, i)
                entries.append(entry)
                i = next_i
                continue

            # 3. Standard Timestamped / Level Line
            ts_match = TIMESTAMPED_LINE_REGEX.match(line)
            if ts_match:
                ts = ts_match.group(1)
                lvl_raw = (ts_match.group(2) or ts_match.group(3) or "INFO").upper()
                msg = ts_match.group(4)

                level = self._normalize_level(lvl_raw)
                trace_id = self._extract_trace_id(msg)

                # If the next line is a traceback, attach timestamp/context directly
                if i + 1 < len(lines) and PYTHON_TRACEBACK_START.match(lines[i + 1]):
                    entry, next_i = self._parse_python_traceback(lines, i + 1)
                    entry.timestamp = ts
                    entry.trace_id = trace_id
                    entries.append(entry)
                    i = next_i
                    continue

                entries.append(
                    LogEntry(
                        timestamp=ts,
                        level=level,
                        message=msg,
                        trace_id=trace_id,
                    )
                )

            # 4. GitHub Actions CI Failure Indicators
            elif "##[error]" in line or "FAIL " in line or "npm ERR!" in line:
                entries.append(
                    LogEntry(
                        level=LogLevel.ERROR,
                        message=line.replace("##[error]", "").strip(),
                        error_type="CIExecutionFailure",
                    )
                )

            i += 1

        # Step 2: Error Clustering
        clusters = self._cluster_errors(entries)

        # Step 3: Synthesis of Observed Facts & Recommendations
        facts = self._synthesize_facts(clusters, entries)
        recommendations = self._synthesize_recommendations(clusters)

        error_cnt = sum(1 for e in entries if e.level in (LogLevel.ERROR, LogLevel.FATAL))
        warn_cnt = sum(1 for e in entries if e.level == LogLevel.WARN)

        return LogAnalysisResult(
            total_entries=len(entries),
            error_count=error_cnt,
            warning_count=warn_cnt,
            clusters=clusters,
            observed_facts=facts,
            inferred_recommendations=recommendations,
        )

    def analyze_file(self, file_path: Path) -> LogAnalysisResult:
        """Reads and analyzes a local log file safely."""
        target_path = Path(file_path).resolve()
        if self.repo_root:
            target_path = validate_contained_path(self.repo_root, target_path)

        text = target_path.read_text(encoding="utf-8", errors="ignore")
        return self.analyze_log_content(text)

    def _parse_python_traceback(self, lines: List[str], start_idx: int) -> Tuple[LogEntry, int]:
        """Collects a complete Python traceback."""
        tb_lines = [lines[start_idx]]
        idx = start_idx + 1
        last_file = None
        last_line = None
        error_type = "PythonException"
        error_msg = "Unknown error"

        while idx < len(lines):
            line = lines[idx]
            tb_lines.append(line)

            frame_match = PYTHON_FRAME_REGEX.match(line)
            if frame_match:
                last_file = frame_match.group(1)
                last_line = int(frame_match.group(2))

            exc_match = PYTHON_EXCEPTION_REGEX.match(line)
            if exc_match:
                error_type = exc_match.group(1)
                error_msg = exc_match.group(2)
                idx += 1
                break

            # Stop if we hit a non-indented line that isn't the exception header
            if not line.startswith(" ") and not line.startswith("\t"):
                break

            idx += 1

        full_tb = "\n".join(tb_lines)
        return (
            LogEntry(
                level=LogLevel.ERROR,
                message=f"{error_type}: {error_msg}",
                error_type=error_type,
                stack_trace=full_tb,
                file_reference=last_file,
                line_number=last_line,
            ),
            idx,
        )

    def _parse_js_stack(self, lines: List[str], start_idx: int) -> Tuple[LogEntry, int]:
        """Collects a JavaScript stack trace."""
        header_match = JS_STACK_START.match(lines[start_idx])
        error_type = header_match.group(1) if header_match else "JavaScriptError"
        error_msg = header_match.group(2) if header_match else lines[start_idx]

        stack_lines = [lines[start_idx]]
        idx = start_idx + 1
        last_file = None
        last_line = None

        while idx < len(lines):
            line = lines[idx]
            if not line.startswith("    at "):
                break
            stack_lines.append(line)
            frame_match = JS_FRAME_REGEX.match(line)
            if frame_match and not last_file:
                last_file = frame_match.group(2)
                last_line = int(frame_match.group(3))
            idx += 1

        return (
            LogEntry(
                level=LogLevel.ERROR,
                message=f"{error_type}: {error_msg}",
                error_type=error_type,
                stack_trace="\n".join(stack_lines),
                file_reference=last_file,
                line_number=last_line,
            ),
            idx,
        )

    def _cluster_errors(self, entries: List[LogEntry]) -> List[ErrorCluster]:
        """Groups errors sharing the same normalized stack trace or error message."""
        clusters_map: Dict[str, ErrorCluster] = {}

        for e in entries:
            if e.level in (LogLevel.ERROR, LogLevel.FATAL):
                # Build normalized signature
                sig_base = e.error_type or "GenericError"
                if e.stack_trace:
                    # Strip variable memory addresses (0x...) and line numbers
                    norm_trace = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", e.stack_trace)
                    norm_trace = re.sub(r":\d+", ":LINE", norm_trace)
                    sig_base += norm_trace
                else:
                    sig_base += e.message

                sig_hash = hashlib.sha256(sig_base.encode("utf-8")).hexdigest()[:12]

                if sig_hash in clusters_map:
                    cluster = clusters_map[sig_hash]
                    cluster.occurrences += 1
                    if e.file_reference and e.file_reference not in cluster.affected_files:
                        cluster.affected_files.append(e.file_reference)
                else:
                    clusters_map[sig_hash] = ErrorCluster(
                        signature_hash=sig_hash,
                        error_type=e.error_type or "Error",
                        representative_message=e.message,
                        occurrences=1,
                        sample_stack_trace=e.stack_trace or e.message,
                        affected_files=[e.file_reference] if e.file_reference else [],
                    )

        # Sort clusters descending by occurrence frequency
        return sorted(list(clusters_map.values()), key=lambda c: c.occurrences, reverse=True)

    def _synthesize_facts(self, clusters: List[ErrorCluster], entries: List[LogEntry]) -> List[str]:
        """Produces verified empirical statements observed in the logs."""
        facts: List[str] = []
        for c in clusters:
            files_str = f" in {', '.join(c.affected_files)}" if c.affected_files else ""
            facts.append(
                f"Observed {c.occurrences} occurrence(s) of '{c.error_type}'{files_str}: {c.representative_message}"
            )
        return facts

    def _synthesize_recommendations(self, clusters: List[ErrorCluster]) -> List[str]:
        """Infers operational recovery suggestions grounded in known error types."""
        recs: List[str] = []
        for c in clusters:
            etype = c.error_type.lower()
            if "connectionrefused" in etype or "econnrefused" in etype:
                recs.append(
                    f"For {c.error_type}: Verify network connectivity, local port bindings, and service startup sequence."
                )
            elif "notfound" in etype or "filenotfound" in etype or "enoent" in etype:
                recs.append(
                    f"For {c.error_type}: Verify that the target resource or file path exists and permissions are granted."
                )
            elif "timeout" in etype or "etimedout" in etype:
                recs.append(
                    f"For {c.error_type}: Check upstream API latency or consider increasing client timeout settings."
                )
            elif "keyerror" in etype or "undefined" in etype:
                recs.append(
                    f"For {c.error_type}: Check payload schemas to ensure expected keys/properties are passed."
                )
        return recs

    def render_troubleshooting_guide(self, analysis: LogAnalysisResult) -> DocProposal:
        """Generates docs/troubleshooting.md from observed log patterns."""
        lines = [
            "# Troubleshooting & Operational Guide",
            "",
            "This guide is synthesized from empirical runtime and CI log analysis.",
            "",
            "## Summary of Observed Failures",
            f"- **Total Log Entries Analyzed**: {analysis.total_entries}",
            f"- **Errors**: {analysis.error_count}",
            f"- **Warnings**: {analysis.warning_count}",
            f"- **Distinct Error Clusters**: {len(analysis.clusters)}",
            "",
            "## Observed Runtime Facts",
            "",
        ]

        anchors: List[EvidenceAnchor] = []

        if analysis.observed_facts:
            for fact in analysis.observed_facts:
                lines.append(f"- {fact}")
        else:
            lines.append("No errors or crashes were detected in analyzed logs.")

        lines.extend([
            "",
            "## Inferred Resolutions & Recommendations",
            "",
        ])

        if analysis.inferred_recommendations:
            for rec in analysis.inferred_recommendations:
                lines.append(f"- {rec}")
        else:
            lines.append("No active error clusters require resolution.")

        lines.extend([
            "",
            "## Repetitive Error Clusters",
            "",
        ])

        for c in analysis.clusters:
            lines.extend([
                f"### [{c.signature_hash}] `{c.error_type}` ({c.occurrences} occurrences)",
                "",
                f"**Message**: {c.representative_message}",
                "",
                "```text",
                c.sample_stack_trace,
                "```",
                "",
            ])
            for af in c.affected_files:
                anchors.append(
                    EvidenceAnchor(
                        source_file=af,
                        rationale=f"Cluster {c.signature_hash} ({c.error_type})"
                    )
                )

        proposal = DocProposal(
            file_path="docs/troubleshooting.md",
            doc_type=DocType.TROUBLESHOOTING,
            proposed_content="\n".join(lines),
            is_new_file=True,
            rationale="Synthesized troubleshooting guide from parsed application/CI log clusters.",
            evidence_anchors=anchors,
        )
        proposal.compute_diff()
        return proposal

    @staticmethod
    def _normalize_level(lvl: str) -> LogLevel:
        lvl = lvl.upper()
        if lvl in ("CRITICAL", "FATAL"):
            return LogLevel.FATAL
        elif lvl in ("ERROR", "ERR"):
            return LogLevel.ERROR
        elif lvl in ("WARN", "WARNING"):
            return LogLevel.WARN
        elif lvl == "DEBUG":
            return LogLevel.DEBUG
        return LogLevel.INFO

    @staticmethod
    def _extract_trace_id(text: str) -> Optional[str]:
        match = TRACE_ID_REGEX.search(text)
        return match.group(1) if match else None
