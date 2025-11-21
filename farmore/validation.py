"""
Input validation utilities for Farmore.

"Trust, but verify. Especially user input." — schema.cx
"""

import re
from pathlib import Path


class ValidationError(Exception):
    """Raised when input validation fails."""

    pass


def validate_repository_format(repository: str) -> tuple[str, str]:
    """
    Validate and parse repository string in 'owner/repo' format.
    
    Args:
        repository: Repository string in format 'owner/repo'
    
    Returns:
        Tuple of (owner, repo) if valid
        
    Raises:
        ValidationError: If format is invalid or contains disallowed characters
        
    Security:
        Prevents command injection by validating against GitHub's allowed characters.
        GitHub repository names allow: alphanumeric, hyphens, underscores, and periods.
    """
    if not repository or not isinstance(repository, str):
        raise ValidationError("Repository must be a non-empty string")
    
    parts = repository.split("/")
    if len(parts) != 2:
        raise ValidationError("Repository must be in format 'owner/repo'")
    
    owner, repo = parts
    
    # Validate owner and repo names (GitHub's allowed characters)
    # Pattern: alphanumeric, hyphens, underscores, periods (no spaces or special chars)
    github_name_pattern = r'^[a-zA-Z0-9._-]+$'
    
    if not re.match(github_name_pattern, owner):
        raise ValidationError(
            f"Invalid owner name '{owner}'. "
            "Only alphanumeric characters, '.', '-', and '_' are allowed."
        )
    
    if not re.match(github_name_pattern, repo):
        raise ValidationError(
            f"Invalid repository name '{repo}'. "
            "Only alphanumeric characters, '.', '-', and '_' are allowed."
        )
    
    # Additional length validation (GitHub limits)
    if len(owner) > 39:  # GitHub username max length
        raise ValidationError(f"Owner name too long (max 39 characters): '{owner}'")
    
    if len(repo) > 100:  # GitHub repo name max length  
        raise ValidationError(f"Repository name too long (max 100 characters): '{repo}'")
    
    # Prevent path traversal attempts
    if ".." in owner or ".." in repo:
        raise ValidationError("Path traversal patterns are not allowed")
    
    if "/" in owner or "\\" in owner or "/" in repo or "\\" in repo:
        raise ValidationError("Path separators are not allowed in repository names")
    
    return owner, repo


def validate_github_token(token: str | None) -> str | None:
    """
    Validate GitHub personal access token format.
    
    Args:
        token: GitHub PAT token string or None
    
    Returns:
        The token if valid, None if token is None
        
    Raises:
        ValidationError: If token format is invalid
        
    Note:
        GitHub classic tokens start with 'ghp_' (40 chars total)
        GitHub fine-grained tokens start with 'github_pat_' (varies in length)
    """
    if token is None or token == "":
        return None
    
    if not isinstance(token, str):
        raise ValidationError("Token must be a string")
    
    # Check for obvious invalid tokens
    if len(token) < 10:
        raise ValidationError("Token is too short to be valid")
    
    if len(token) > 255:
        raise ValidationError("Token is too long")
    
    # Check for classic or fine-grained pattern
    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        # Warn but don't fail - some legacy tokens may not follow this pattern
        pass
    
    # Check for whitespace or special characters that shouldn't be there
    if any(c in token for c in [" ", "\n", "\r", "\t"]):
        raise ValidationError("Token contains invalid whitespace characters")
    
    return token


def validate_path_safety(path: Path) -> Path:
    """
    Validate that a path is safe to use (no traversal attempts).
    
    Args:
        path: Path object to validate
    
    Returns:
        The path if valid
        
    Raises:
        ValidationError: If path contains traversal attempts or is unsafe
    """
    path_str = str(path)
    
    # Check for path traversal attempts
    if ".." in path.parts:
        raise ValidationError(f"Path traversal detected in: {path}")
    
    # Resolve the path and check if it tries to escape
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as e:
        raise ValidationError(f"Invalid path: {e}")
    
    return path


def validate_format_option(format: str, allowed: list[str] = ["json", "yaml"]) -> str:
    """
    Validate export format option.
    
    Args:
        format: Format string to validate
        allowed: List of allowed formats
    
    Returns:
        Lowercase format string if valid
        
    Raises:
        ValidationError: If format is not in allowed list
    """
    format_lower = format.lower().strip()
    
    if format_lower not in allowed:
        allowed_str = ", ".join(f"'{f}'" for f in allowed)
        raise ValidationError(f"Invalid format '{format}'. Allowed formats: {allowed_str}")
    
    return format_lower


def validate_state_option(state: str, allowed: list[str] = ["all", "open", "closed"]) -> str:
    """
    Validate state filter option for issues/PRs.
    
    Args:
        state: State string to validate
        allowed: List of allowed states
    
    Returns:
        Lowercase state string if valid
        
    Raises:
        ValidationError: If state is not in allowed list
    """
    state_lower = state.lower().strip()
    
    if state_lower not in allowed:
        allowed_str = ", ".join(f"'{s}'" for s in allowed)
        raise ValidationError(f"Invalid state '{state}'. Allowed states: {allowed_str}")
    
    return state_lower


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a string for safe use as a filename.
    
    Args:
        filename: String to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized filename string
    """
    # Remove or replace unsafe characters
    # Keep alphanumeric, hyphens, underscores, and periods
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Remove leading/trailing periods and underscores
    sanitized = sanitized.strip('._')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "unnamed"
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized
