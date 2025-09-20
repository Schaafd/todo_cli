"""Datetime utilities with consistent UTC timezone handling.

This module provides centralized datetime functions to ensure all datetime
operations in the Todo CLI are timezone-aware and use UTC consistently.
"""

from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    """Return current datetime in UTC timezone.
    
    Returns:
        Current datetime with timezone=UTC
    """
    return datetime.now(timezone.utc)


def ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware, assuming UTC if naive.
    
    Args:
        dt: Datetime to check/convert, or None
        
    Returns:
        Timezone-aware datetime in UTC, or None if input was None
    """
    if dt is None:
        return None
    
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    
    # Already timezone-aware
    return dt


def min_utc() -> datetime:
    """Return datetime.min with UTC timezone for sorting fallbacks.
    
    Returns:
        datetime.min with timezone=UTC
    """
    return datetime.min.replace(tzinfo=timezone.utc)


def max_utc() -> datetime:
    """Return datetime.max with UTC timezone for sorting fallbacks.
    
    Returns:
        datetime.max with timezone=UTC
    """
    return datetime.max.replace(tzinfo=timezone.utc)


def parse_date_with_tz(date_str: str, date_format: str = "%Y-%m-%d") -> datetime:
    """Parse date string and ensure it's timezone-aware (UTC).
    
    Args:
        date_str: Date string to parse
        date_format: Format string for parsing (default: YYYY-MM-DD)
        
    Returns:
        Timezone-aware datetime in UTC
    """
    parsed = datetime.strptime(date_str, date_format)
    return ensure_aware(parsed)


def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO string with timezone info.
    
    Args:
        dt: Datetime to convert, or None
        
    Returns:
        ISO format string with timezone, or None if input was None
    """
    if dt is None:
        return None
    
    aware_dt = ensure_aware(dt)
    return aware_dt.isoformat()


def normalize_datetime_dict(data: dict, fields: list) -> dict:
    """Normalize datetime fields in a dictionary to be timezone-aware.
    
    Args:
        data: Dictionary containing datetime fields
        fields: List of field names to normalize
        
    Returns:
        Dictionary with normalized datetime fields
    """
    normalized = data.copy()
    
    for field in fields:
        if field in normalized and normalized[field] is not None:
            if isinstance(normalized[field], str):
                try:
                    # Try to parse ISO format
                    normalized[field] = datetime.fromisoformat(normalized[field])
                except ValueError:
                    # Try standard date format
                    try:
                        normalized[field] = parse_date_with_tz(normalized[field])
                    except ValueError:
                        # Skip if can't parse
                        continue
            
            if isinstance(normalized[field], datetime):
                normalized[field] = ensure_aware(normalized[field])
    
    return normalized