"""
Security utilities for DocMCP.

Provides security-related helper functions.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from pathlib import Path
from typing import Optional


def hash_content(content: bytes, algorithm: str = "sha256") -> str:
    """
    Hash content using specified algorithm.
    
    Args:
        content: Content to hash
        algorithm: Hash algorithm (sha256, sha512, md5)
        
    Returns:
        Hex digest of hash
    """
    if algorithm == "sha256":
        return hashlib.sha256(content).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(content).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(content).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique identifier.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Unique identifier string
    """
    unique_id = str(uuid.uuid4()).replace("-", "")
    if prefix:
        return f"{prefix}_{unique_id[:16]}"
    return unique_id[:16]


def generate_token(length: int = 32) -> str:
    """
    Generate a secure random token.
    
    Args:
        length: Token length
        
    Returns:
        Secure random token
    """
    return secrets.token_urlsafe(length)


def verify_hmac(
    message: bytes,
    signature: bytes,
    secret: bytes,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify HMAC signature.
    
    Args:
        message: Original message
        signature: Signature to verify
        secret: Secret key
        algorithm: Hash algorithm
        
    Returns:
        True if signature is valid
    """
    expected = hmac.new(secret, message, getattr(hashlib, algorithm)).digest()
    return hmac.compare_digest(expected, signature)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe use.
    
    Removes or replaces dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove path separators and null bytes
    sanitized = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
    
    # Remove leading dots (hidden files)
    sanitized = sanitized.lstrip(".")
    
    # Limit length
    max_length = 255
    if len(sanitized) > max_length:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        sanitized = name[:max_length - len(ext)] + ext
    
    # If empty, use default
    if not sanitized:
        sanitized = "unnamed"
    
    return sanitized


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")
    
    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain at least one uppercase letter")
    
    if not re.search(r"[a-z]", password):
        issues.append("Password must contain at least one lowercase letter")
    
    if not re.search(r"\d", password):
        issues.append("Password must contain at least one digit")
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        issues.append("Password must contain at least one special character")
    
    return len(issues) == 0, issues


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging.
    
    Args:
        data: Data to mask
        visible_chars: Number of characters to keep visible
        
    Returns:
        Masked data
    """
    if len(data) <= visible_chars * 2:
        return "*" * len(data)
    
    return data[:visible_chars] + "*" * (len(data) - visible_chars * 2) + data[-visible_chars:]


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare strings in constant time to prevent timing attacks.
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        True if strings are equal
    """
    return hmac.compare_digest(a.encode(), b.encode())
