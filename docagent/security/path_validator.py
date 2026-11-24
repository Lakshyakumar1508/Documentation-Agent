"""Filesystem path validation and containment boundaries."""

import os
from pathlib import Path
from typing import Union
from docagent.core.exceptions import PathTraversalError


def validate_contained_path(
    base_dir: Union[str, Path],
    target_path: Union[str, Path],
    allow_nonexistent: bool = False
) -> Path:
    """
    Validates that target_path is strictly contained within base_dir.
    
    Prevents directory traversal attacks (e.g. '../', symlinks pointing outside base_dir).
    
    Args:
        base_dir: The authorized root directory.
        target_path: The file or directory path to validate.
        allow_nonexistent: If True, validates parent containment for a file that will be written.
        
    Returns:
        Path: The validated absolute canonical Path.
        
    Raises:
        PathTraversalError: If the target path resolves outside base_dir.
    """
    base_resolved = Path(base_dir).resolve()
    
    if not base_resolved.exists():
        raise PathTraversalError(f"Authorized base directory does not exist: {base_resolved}")

    # Resolve target path
    target = Path(target_path)
    if not target.is_absolute():
        target = (base_resolved / target).resolve()
    else:
        target = target.resolve()

    # If the target doesn't exist yet, validate its existing parent directory
    check_path = target if not allow_nonexistent or target.exists() else target.parent.resolve()

    try:
        # Check relative_to containment
        check_path.relative_to(base_resolved)
    except ValueError:
        raise PathTraversalError(
            f"Access denied: Path '{target}' resolves outside authorized root '{base_resolved}'"
        )

    return target
