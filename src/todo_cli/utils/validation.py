"""Timezone validation utilities for Todo CLI.

This module provides comprehensive validation for datetime fields to ensure
all datetime objects are timezone-aware and consistent throughout the application.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple, Any, Dict
from dataclasses import fields

logger = logging.getLogger(__name__)


class DateTimeValidationError(Exception):
    """Exception raised when datetime validation fails."""
    
    def __init__(self, message: str, field_name: str, value: Any, suggestions: List[str] = None):
        self.field_name = field_name
        self.value = value
        self.suggestions = suggestions or []
        super().__init__(message)


class DateTimeValidator:
    """Comprehensive datetime validation for Todo CLI objects."""
    
    def __init__(self, strict_mode: bool = False):
        """Initialize the validator.
        
        Args:
            strict_mode: If True, raise exceptions on validation failures.
                        If False, log warnings and attempt to fix issues.
        """
        self.strict_mode = strict_mode
        self.validation_errors = []
        self.validation_warnings = []
    
    def validate_datetime_field(self, field_name: str, value: Any, 
                              allow_none: bool = True) -> Optional[datetime]:
        """Validate a single datetime field.
        
        Args:
            field_name: Name of the field being validated
            value: The datetime value to validate
            allow_none: Whether None values are acceptable
            
        Returns:
            The validated datetime (timezone-aware) or None
            
        Raises:
            DateTimeValidationError: If strict_mode is True and validation fails
        """
        if value is None:
            if allow_none:
                return None
            else:
                error_msg = f"Field '{field_name}' cannot be None"
                self._handle_error(error_msg, field_name, value, [
                    "Provide a valid datetime object",
                    "Use now_utc() for current time"
                ])
                return None
        
        if not isinstance(value, datetime):
            error_msg = f"Field '{field_name}' must be a datetime object, got {type(value).__name__}"
            self._handle_error(error_msg, field_name, value, [
                "Convert the value to a datetime object",
                "Use datetime.fromisoformat() for ISO strings",
                "Use parse_datetime() utility function"
            ])
            return None
        
        # Check if timezone-aware
        if value.tzinfo is None:
            error_msg = f"Field '{field_name}' has naive datetime: {value}"
            suggestions = [
                "Use ensure_aware() to add timezone info",
                "Use now_utc() for current time in UTC",
                "Parse with timezone info using datetime.fromisoformat()"
            ]
            
            if self.strict_mode:
                self._handle_error(error_msg, field_name, value, suggestions)
                return None
            else:
                # In non-strict mode, try to fix by assuming UTC
                try:
                    from .datetime import ensure_aware
                    fixed_value = ensure_aware(value)
                    self.validation_warnings.append({
                        'field': field_name,
                        'message': f"Auto-fixed naive datetime to UTC: {value} → {fixed_value}",
                        'original_value': value,
                        'fixed_value': fixed_value
                    })
                    return fixed_value
                except ImportError:
                    # Fallback if circular import
                    from datetime import timezone
                    fixed_value = value.replace(tzinfo=timezone.utc)
                    self.validation_warnings.append({
                        'field': field_name,
                        'message': f"Auto-fixed naive datetime to UTC: {value} → {fixed_value}",
                        'original_value': value,
                        'fixed_value': fixed_value
                    })
                    return fixed_value
        
        # Check if timezone is reasonable (not far in future/past from UTC)
        utc_offset_hours = value.utcoffset().total_seconds() / 3600 if value.utcoffset() else 0
        if abs(utc_offset_hours) > 14:  # UTC-12 to UTC+14 are valid
            warning_msg = f"Field '{field_name}' has unusual timezone offset: {utc_offset_hours}h"
            self.validation_warnings.append({
                'field': field_name,
                'message': warning_msg,
                'value': value,
                'offset_hours': utc_offset_hours
            })
        
        return value
    
    def validate_todo_datetimes(self, todo) -> Dict[str, Any]:
        """Validate all datetime fields in a Todo object.
        
        Args:
            todo: Todo object to validate
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'fixed_fields': {}
        }
        
        # Reset validation state
        self.validation_errors = []
        self.validation_warnings = []
        
        # Define datetime fields and their constraints
        datetime_fields = [
            ('created', False),          # Required field
            ('modified', False),         # Required field  
            ('start_date', True),        # Optional
            ('due_date', True),          # Optional
            ('scheduled_date', True),    # Optional
            ('defer_until', True),       # Optional
            ('completed_date', True),    # Optional
            ('next_due', True),          # Optional
        ]
        
        for field_name, allow_none in datetime_fields:
            if hasattr(todo, field_name):
                original_value = getattr(todo, field_name)
                validated_value = self.validate_datetime_field(
                    field_name, original_value, allow_none
                )
                
                # Update the field if it was fixed
                if validated_value != original_value:
                    setattr(todo, field_name, validated_value)
                    results['fixed_fields'][field_name] = {
                        'original': original_value,
                        'fixed': validated_value
                    }
        
        # Add validation results
        results['errors'] = self.validation_errors
        results['warnings'] = self.validation_warnings
        results['valid'] = len(self.validation_errors) == 0
        
        return results
    
    def validate_project_datetimes(self, project) -> Dict[str, Any]:
        """Validate all datetime fields in a Project object.
        
        Args:
            project: Project object to validate
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'fixed_fields': {}
        }
        
        # Reset validation state
        self.validation_errors = []
        self.validation_warnings = []
        
        # Define datetime fields for Project
        datetime_fields = [
            ('created', False),            # Required field
            ('modified', False),           # Required field
            ('deadline', True),            # Optional
            ('sync_last_update', True),    # Optional
        ]
        
        for field_name, allow_none in datetime_fields:
            if hasattr(project, field_name):
                original_value = getattr(project, field_name)
                validated_value = self.validate_datetime_field(
                    field_name, original_value, allow_none
                )
                
                # Update the field if it was fixed
                if validated_value != original_value:
                    setattr(project, field_name, validated_value)
                    results['fixed_fields'][field_name] = {
                        'original': original_value,
                        'fixed': validated_value
                    }
        
        results['errors'] = self.validation_errors
        results['warnings'] = self.validation_warnings
        results['valid'] = len(self.validation_errors) == 0
        
        return results
    
    def _handle_error(self, message: str, field_name: str, value: Any, suggestions: List[str]):
        """Handle validation errors based on strict_mode setting."""
        error_info = {
            'field': field_name,
            'message': message,
            'value': value,
            'suggestions': suggestions
        }
        
        if self.strict_mode:
            self.validation_errors.append(error_info)
            raise DateTimeValidationError(message, field_name, value, suggestions)
        else:
            self.validation_errors.append(error_info)
            logger.error(f"DateTime validation error: {message}")
    
    def get_validation_summary(self) -> str:
        """Get a human-readable summary of validation results."""
        lines = []
        
        if self.validation_errors:
            lines.append(f"❌ {len(self.validation_errors)} validation errors:")
            for error in self.validation_errors:
                lines.append(f"  • {error['field']}: {error['message']}")
                for suggestion in error['suggestions']:
                    lines.append(f"    💡 {suggestion}")
        
        if self.validation_warnings:
            lines.append(f"⚠️  {len(self.validation_warnings)} warnings:")
            for warning in self.validation_warnings:
                lines.append(f"  • {warning['field']}: {warning['message']}")
        
        if not self.validation_errors and not self.validation_warnings:
            lines.append("✅ All datetime validations passed!")
        
        return "\n".join(lines)


def validate_todo_datetimes(todo, strict_mode: bool = False) -> Dict[str, Any]:
    """Convenience function to validate a Todo object's datetime fields.
    
    Args:
        todo: Todo object to validate
        strict_mode: Whether to raise exceptions on validation failures
        
    Returns:
        Dictionary with validation results
    """
    validator = DateTimeValidator(strict_mode=strict_mode)
    return validator.validate_todo_datetimes(todo)


def validate_project_datetimes(project, strict_mode: bool = False) -> Dict[str, Any]:
    """Convenience function to validate a Project object's datetime fields.
    
    Args:
        project: Project object to validate
        strict_mode: Whether to raise exceptions on validation failures
        
    Returns:
        Dictionary with validation results
    """
    validator = DateTimeValidator(strict_mode=strict_mode)
    return validator.validate_project_datetimes(project)


def validate_datetime_consistency(*datetime_values) -> bool:
    """Validate that multiple datetime values are all timezone-aware.
    
    Args:
        *datetime_values: Variable number of datetime values to check
        
    Returns:
        True if all non-None values are timezone-aware, False otherwise
    """
    for dt in datetime_values:
        if dt is not None and isinstance(dt, datetime) and dt.tzinfo is None:
            return False
    return True


def get_naive_datetime_fields(obj) -> List[Tuple[str, datetime]]:
    """Get list of fields in an object that contain naive datetimes.
    
    Args:
        obj: Object to inspect (Todo, Project, etc.)
        
    Returns:
        List of (field_name, datetime_value) tuples for naive datetime fields
    """
    naive_fields = []
    
    # Check all attributes of the object
    for attr_name in dir(obj):
        if attr_name.startswith('_'):
            continue
        
        try:
            value = getattr(obj, attr_name)
            if isinstance(value, datetime) and value.tzinfo is None:
                naive_fields.append((attr_name, value))
        except (AttributeError, TypeError):
            continue
    
    return naive_fields


if __name__ == "__main__":
    # Example usage and testing
    from datetime import datetime, timezone
    
    # Test with naive datetime
    naive_dt = datetime(2023, 12, 25, 10, 30)
    aware_dt = datetime(2023, 12, 25, 10, 30, tzinfo=timezone.utc)
    
    validator = DateTimeValidator(strict_mode=False)
    
    # Test individual field validation
    result1 = validator.validate_datetime_field("test_naive", naive_dt)
    result2 = validator.validate_datetime_field("test_aware", aware_dt)
    
    print("Validation Summary:")
    print(validator.get_validation_summary())