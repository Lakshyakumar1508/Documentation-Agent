"""Custom exception definitions for DocAgent."""


class DocAgentError(Exception):
    """Base exception class for all DocAgent errors."""
    pass


class SecurityViolationError(DocAgentError):
    """Raised when an operation breaches security containment or authorization."""
    pass


class PathTraversalError(SecurityViolationError):
    """Raised when a resolved file path falls outside the authorized workspace."""
    pass


class SecretDetectedError(SecurityViolationError):
    """Raised when an unredacted secret is caught in a critical operation."""
    pass


class AnalysisError(DocAgentError):
    """Raised when repository scanning or code parsing fails fatally."""
    pass


class ValidationError(DocAgentError):
    """Raised when documentation claim validation encounters critical blocking errors."""
    pass


class OrchestrationError(DocAgentError):
    """Raised when the LangGraph workflow execution fails or times out."""
    pass


class WebhookVerificationError(SecurityViolationError):
    """Raised when a webhook signature fails HMAC verification."""
    pass
