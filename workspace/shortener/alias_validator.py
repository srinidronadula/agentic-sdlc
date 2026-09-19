import re
from typing import Optional

from shortener import db

# Reserved aliases that map to API endpoints or system routes
RESERVED_ALIASES = {
    "shorten",
    "health",
    "api",
    "admin",
    "docs",
    "swagger",
    "redirect",
    "static",
    "assets",
    "auth",
    "login",
    "logout",
    "stats",
}

# Regex: lowercase alphanumeric and hyphens, 3-50 chars, no leading/trailing hyphens
ALIAS_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9\-]{1,48}[a-z0-9])?$")


def validate_alias_format(alias: str) -> tuple[bool, Optional[str]]:
    """
    Validate alias format.
    
    Args:
        alias: The alias to validate
        
    Returns:
        (is_valid, error_message) tuple. error_message is None if valid.
    """
    if not isinstance(alias, str):
        return False, "Alias must be a string"
    
    alias = alias.strip()
    
    if not alias:
        return False, "Alias cannot be empty"
    
    # Check length
    if len(alias) < 3 or len(alias) > 50:
        return False, "Alias must be 3-50 characters long"
    
    # Check format (lowercase alphanumeric + hyphens, no leading/trailing hyphens)
    if not ALIAS_PATTERN.match(alias):
        return False, "Alias must contain only lowercase letters, numbers, and hyphens (no leading/trailing hyphens)"
    
    return True, None


def is_alias_reserved(alias: str) -> bool:
    """
    Check if alias is in the reserved list.
    
    Args:
        alias: The alias to check
        
    Returns:
        True if reserved, False otherwise
    """
    return alias.lower() in RESERVED_ALIASES


def is_alias_taken(alias: str) -> bool:
    """
    Check if alias already exists in database.
    
    Args:
        alias: The alias to check
        
    Returns:
        True if taken, False otherwise
    """
    return db.alias_exists(alias)


def validate_alias(alias: Optional[str]) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Orchestrate all alias validation checks.
    
    Args:
        alias: The alias to validate (can be None)
        
    Returns:
        (is_valid, error_message, error_code) tuple.
        error_message and error_code are None if valid.
        error_code is one of: 'format', 'reserved', 'taken'
    """
    if alias is None:
        return True, None, None
    
    # Validate format
    is_valid, error_msg = validate_alias_format(alias)
    if not is_valid:
        return False, error_msg, "format"
    
    # Check reserved
    if is_alias_reserved(alias):
        return False, "Alias is reserved", "reserved"
    
    # Check if taken
    if is_alias_taken(alias):
        return False, "Alias already taken", "taken"
    
    return True, None, None
