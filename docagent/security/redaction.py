"""Automated secret and credential redaction engine."""

import re
from typing import Any, Dict, List, Pattern, Tuple, Union

# Compiled regex patterns for detecting secrets
REDACTION_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    # AWS Access Key ID
    ("AWS_KEY", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    # AWS Secret Key
    ("AWS_SECRET", re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?")),
    # GitHub Personal Access Token (classic & fine-grained)
    ("GITHUB_TOKEN", re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,255})\b")),
    # Slack Token
    ("SLACK_TOKEN", re.compile(r"\b(xox[p|b|o|a]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32})\b")),
    # Private Key Headers
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----[\s\S]+?-----END (?:[A-Z0-9_-]+ )?PRIVATE KEY-----")),
    # Generic Bearer Tokens
    ("BEARER_TOKEN", re.compile(r"(?i)\bbearer\s+([a-zA-Z0-9_\-\.]{25,})\b")),
    # Database Connection Strings with Passwords
    ("DB_CONNECTION", re.compile(r"(?i)\b((?:postgres|postgresql|mysql|mongodb|redis|mssql):\/\/[^:\/\s]+:)([^@\/\s]+)(@[^ \/\s]+)")),
    # Common Key=Value secret definitions
    ("GENERIC_SECRET", re.compile(
        r"(?i)\b(api_key|apikey|secret|password|passwd|auth_token|access_token|private_key)\s*[:=]\s*['\"]?([^\s'\",]{4,})['\"]?"
    )),
    # User:Password credentials pattern in logs (e.g. user admin:password123)
    ("USER_PASSWORD", re.compile(
        r"(?i)\b(user(?:name)?|login)\s+([a-zA-Z0-9_\-\.]+):([a-zA-Z0-9_\-\.!@#$%^&*]{4,})\b"
    )),
]


class RedactionEngine:
    """Scrubs sensitive credentials and tokens from logs, code comments, and docs."""

    @classmethod
    def redact_text(cls, text: str) -> str:
        """
        Redacts all matching secrets from a raw string.
        
        Args:
            text: Unsanitized input text.
            
        Returns:
            Sanitized text with tokens replaced by [REDACTED:<CATEGORY>].
        """
        if not text:
            return text

        scrubbed = text

        for category, pattern in REDACTION_PATTERNS:
            if category == "DB_CONNECTION":
                # Only redact the password portion in connection strings
                scrubbed = pattern.sub(r"\1[REDACTED:PASSWORD]\3", scrubbed)
            elif category == "USER_PASSWORD":
                scrubbed = pattern.sub(r"\1 \2:[REDACTED:PASSWORD]", scrubbed)
            elif category == "GENERIC_SECRET":
                # Redact the value portion while preserving the key name
                scrubbed = pattern.sub(r"\1=[REDACTED:SECRET]", scrubbed)
            elif category == "AWS_SECRET":
                scrubbed = pattern.sub(r"aws_secret_access_key=[REDACTED:AWS_SECRET]", scrubbed)
            else:
                scrubbed = pattern.sub(f"[REDACTED:{category}]", scrubbed)

        return scrubbed

    @classmethod
    def redact_structure(cls, data: Any) -> Any:
        """Recursively redacts secrets in dicts, lists, and primitives."""
        if isinstance(data, str):
            return cls.redact_text(data)
        elif isinstance(data, dict):
            return {k: cls.redact_structure(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.redact_structure(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(cls.redact_structure(item) for item in data)
        return data
