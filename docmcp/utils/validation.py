"""
Validation utilities for DocMCP.

Provides common validation functions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


# Email validation regex (simplified)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# URL validation regex
URL_REGEX = re.compile(
    r"^https?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
    r"localhost|"  # localhost
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"
    
    if len(email) > 254:
        return False, "Email is too long"
    
    if not EMAIL_REGEX.match(email):
        return False, "Invalid email format"
    
    return True, None


def validate_url(url: str, allowed_schemes: Optional[list] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate URL.
    
    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: http, https)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL is required"
    
    allowed_schemes = allowed_schemes or ["http", "https"]
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            return False, "URL must have a scheme"
        
        if parsed.scheme not in allowed_schemes:
            return False, f"URL scheme must be one of: {', '.join(allowed_schemes)}"
        
        if not parsed.netloc:
            return False, "URL must have a host"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid URL: {e}"


def validate_file_path(
    path: str,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_directory: bool = False,
    allowed_extensions: Optional[list] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate file path.
    
    Args:
        path: Path to validate
        must_exist: Whether path must exist
        must_be_file: Whether path must be a file
        must_be_directory: Whether path must be a directory
        allowed_extensions: List of allowed file extensions
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path is required"
    
    try:
        path_obj = Path(path)
        
        # Check existence
        if must_exist and not path_obj.exists():
            return False, f"Path does not exist: {path}"
        
        # Check type
        if must_be_file and path_obj.exists() and not path_obj.is_file():
            return False, f"Path is not a file: {path}"
        
        if must_be_directory and path_obj.exists() and not path_obj.is_dir():
            return False, f"Path is not a directory: {path}"
        
        # Check extension
        if allowed_extensions:
            ext = path_obj.suffix.lower()
            allowed = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in allowed_extensions]
            if ext not in allowed:
                return False, f"File extension must be one of: {', '.join(allowed_extensions)}"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid path: {e}"


def validate_document_id(doc_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate document ID format.
    
    Args:
        doc_id: Document ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not doc_id:
        return False, "Document ID is required"
    
    if len(doc_id) < 8:
        return False, "Document ID is too short"
    
    # Check for valid characters (alphanumeric, hyphen, underscore)
    if not re.match(r"^[a-zA-Z0-9_-]+$", doc_id):
        return False, "Document ID contains invalid characters"
    
    return True, None


def validate_mime_type(
    mime_type: str,
    allowed_types: Optional[list] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate MIME type.
    
    Args:
        mime_type: MIME type to validate
        allowed_types: List of allowed MIME types
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not mime_type:
        return False, "MIME type is required"
    
    # Basic MIME type format check
    if not re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9.]*/[a-zA-Z0-9][-a-zA-Z0-9.+]*$", mime_type):
        return False, "Invalid MIME type format"
    
    if allowed_types and mime_type not in allowed_types:
        return False, f"MIME type must be one of: {', '.join(allowed_types)}"
    
    return True, None


def validate_file_size(
    size_bytes: int,
    max_size_mb: float,
    min_size_bytes: int = 0,
) -> Tuple[bool, Optional[str]]:
    """
    Validate file size.
    
    Args:
        size_bytes: File size in bytes
        max_size_mb: Maximum allowed size in MB
        min_size_bytes: Minimum allowed size in bytes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if size_bytes < 0:
        return False, "File size cannot be negative"
    
    if size_bytes < min_size_bytes:
        return False, f"File size must be at least {min_size_bytes} bytes"
    
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    if size_bytes > max_size_bytes:
        return False, f"File size exceeds maximum of {max_size_mb} MB"
    
    return True, None


def sanitize_string(
    value: str,
    max_length: int = 255,
    allow_newlines: bool = False,
) -> str:
    """
    Sanitize a string value.
    
    Args:
        value: String to sanitize
        max_length: Maximum length
        allow_newlines: Whether to allow newline characters
        
    Returns:
        Sanitized string
    """
    if not value:
        return ""
    
    # Remove control characters
    if allow_newlines:
        sanitized = "".join(c for c in value if c == "\n" or c >= " ")
    else:
        sanitized = "".join(c for c in value if c >= " ")
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized
