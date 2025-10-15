"""Theme registry for managing built-in and user themes.

This module provides the ThemeRegistry class for discovering, loading, and
caching theme definitions from built-in presets and user customizations.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from functools import lru_cache
import logging

from .schema import (
    ThemeDefinition,
    ThemeVariant, 
    UserThemeOverrides,
    TerminalCapability,
    IconPack
)
from .utils import deep_merge_dict

logger = logging.getLogger(__name__)


class ThemeRegistry:
    """Registry for theme definitions and user customizations."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the theme registry.
        
        Args:
            config_dir: Optional custom config directory path
        """
        # Get package directory for built-in themes
        self.package_dir = Path(__file__).parent.parent
        self.builtin_themes_dir = self.package_dir / "theme_presets"
        
        # User themes directory
        if config_dir:
            self.user_themes_dir = Path(config_dir) / "themes"
        else:
            self.user_themes_dir = Path.home() / ".todo" / "themes"
        
        # Ensure user themes directory exists
        self.user_themes_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded themes
        self._theme_cache: Dict[str, ThemeDefinition] = {}
        self._variant_cache: Dict[str, Dict[str, ThemeVariant]] = {}
        
        # Available themes catalog
        self._builtin_themes: Set[str] = set()
        self._user_themes: Set[str] = set()
        
        # Scan for available themes
        self._scan_builtin_themes()
        self._scan_user_themes()
    
    def _scan_builtin_themes(self) -> None:
        """Scan for built-in theme files."""
        self._builtin_themes.clear()
        
        if not self.builtin_themes_dir.exists():
            logger.warning(f"Built-in themes directory not found: {self.builtin_themes_dir}")
            return
        
        for theme_file in self.builtin_themes_dir.glob("*.yaml"):
            theme_name = theme_file.stem
            self._builtin_themes.add(theme_name)
            logger.debug(f"Found built-in theme: {theme_name}")
    
    def _scan_user_themes(self) -> None:
        """Scan for user theme files."""
        self._user_themes.clear()
        
        for theme_file in self.user_themes_dir.glob("*.yaml"):
            theme_name = theme_file.stem
            self._user_themes.add(theme_name)
            logger.debug(f"Found user theme: {theme_name}")
        
        for theme_file in self.user_themes_dir.glob("*.json"):
            theme_name = theme_file.stem
            self._user_themes.add(theme_name)
            logger.debug(f"Found user theme: {theme_name}")
    
    def list_available_themes(self) -> List[Dict[str, Any]]:
        """List all available themes with metadata.
        
        Returns:
            List of theme info dictionaries
        """
        themes = []
        
        # Add built-in themes
        for theme_name in sorted(self._builtin_themes):
            try:
                theme_def = self.load_theme_definition(theme_name)
                themes.append({
                    'name': theme_name,
                    'display_name': theme_def.display_name,
                    'description': theme_def.description,
                    'author': theme_def.author,
                    'version': theme_def.version,
                    'type': 'builtin',
                    'variants': [v.name for v in theme_def.variants],
                    'min_capability': theme_def.min_capability.value
                })
            except Exception as e:
                logger.error(f"Error loading theme {theme_name}: {e}")
                themes.append({
                    'name': theme_name,
                    'display_name': theme_name,
                    'description': f"Error loading theme: {e}",
                    'type': 'builtin',
                    'error': True
                })
        
        # Add user themes
        for theme_name in sorted(self._user_themes):
            if theme_name in self._builtin_themes:
                continue  # Skip user overrides of built-in themes for listing
                
            try:
                theme_def = self.load_theme_definition(theme_name)
                themes.append({
                    'name': theme_name,
                    'display_name': theme_def.display_name,
                    'description': theme_def.description,
                    'author': theme_def.author,
                    'version': theme_def.version,
                    'type': 'user',
                    'variants': [v.name for v in theme_def.variants],
                    'extends': theme_def.extends
                })
            except Exception as e:
                logger.error(f"Error loading user theme {theme_name}: {e}")
                themes.append({
                    'name': theme_name,
                    'display_name': theme_name,
                    'description': f"Error loading theme: {e}",
                    'type': 'user',
                    'error': True
                })
        
        return themes
    
    def theme_exists(self, theme_name: str) -> bool:
        """Check if a theme exists.
        
        Args:
            theme_name: Name of the theme to check
            
        Returns:
            True if theme exists
        """
        return theme_name in self._builtin_themes or theme_name in self._user_themes
    
    def get_theme_variants(self, theme_name: str) -> List[str]:
        """Get available variants for a theme.
        
        Args:
            theme_name: Name of the theme
            
        Returns:
            List of variant names
        """
        if theme_name in self._variant_cache:
            return list(self._variant_cache[theme_name].keys())
        
        try:
            theme_def = self.load_theme_definition(theme_name)
            return [v.name for v in theme_def.variants]
        except Exception:
            return []
    
    def load_theme_definition(self, theme_name: str) -> ThemeDefinition:
        """Load a theme definition from file.
        
        Args:
            theme_name: Name of the theme to load
            
        Returns:
            ThemeDefinition instance
            
        Raises:
            FileNotFoundError: If theme file not found
            ValueError: If theme definition is invalid
        """
        # Check cache first
        if theme_name in self._theme_cache:
            return self._theme_cache[theme_name]
        
        theme_data = self._load_theme_file(theme_name)
        theme_def = self._parse_theme_data(theme_data, theme_name)
        
        # Cache the result
        self._theme_cache[theme_name] = theme_def
        
        # Cache variants
        if theme_def.variants:
            self._variant_cache[theme_name] = {
                v.name: v for v in theme_def.variants
            }
        
        return theme_def
    
    def _load_theme_file(self, theme_name: str) -> Dict[str, Any]:
        """Load raw theme data from file.
        
        Args:
            theme_name: Name of the theme file to load
            
        Returns:
            Raw theme data dictionary
            
        Raises:
            FileNotFoundError: If theme file not found
        """
        # Try user themes first
        user_yaml_path = self.user_themes_dir / f"{theme_name}.yaml"
        user_json_path = self.user_themes_dir / f"{theme_name}.json"
        
        if user_yaml_path.exists():
            return self._load_yaml_file(user_yaml_path)
        elif user_json_path.exists():
            return self._load_json_file(user_json_path)
        
        # Try built-in themes
        builtin_path = self.builtin_themes_dir / f"{theme_name}.yaml"
        if builtin_path.exists():
            return self._load_yaml_file(builtin_path)
        
        raise FileNotFoundError(f"Theme '{theme_name}' not found")
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading {file_path}: {e}")
    
    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load JSON file safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading {file_path}: {e}")
    
    def _parse_theme_data(self, theme_data: Dict[str, Any], theme_name: str) -> ThemeDefinition:
        """Parse raw theme data into ThemeDefinition.
        
        Args:
            theme_data: Raw theme data dictionary
            theme_name: Name of the theme (for error reporting)
            
        Returns:
            Parsed ThemeDefinition
            
        Raises:
            ValueError: If theme data is invalid
        """
        try:
            # Handle theme inheritance
            if theme_data.get('extends'):
                base_theme_name = theme_data['extends']
                if base_theme_name != theme_name:  # Prevent circular references
                    base_theme = self.load_theme_definition(base_theme_name)
                    base_data = base_theme.dict()
                    
                    # Remove metadata from base
                    for key in ['name', 'display_name', 'author', 'version']:
                        base_data.pop(key, None)
                    
                    # Deep merge with base theme
                    theme_data = deep_merge_dict(base_data, theme_data)
            
            # Set default name if not provided
            if 'name' not in theme_data:
                theme_data['name'] = theme_name
            
            if 'display_name' not in theme_data:
                theme_data['display_name'] = theme_name.replace('_', ' ').title()
            
            return ThemeDefinition(**theme_data)
            
        except Exception as e:
            raise ValueError(f"Invalid theme definition for '{theme_name}': {e}")
    
    def save_user_theme(self, theme_def: ThemeDefinition, overwrite: bool = False) -> None:
        """Save a user theme definition to file.
        
        Args:
            theme_def: Theme definition to save
            overwrite: Whether to overwrite existing themes
            
        Raises:
            FileExistsError: If theme exists and overwrite=False
        """
        theme_path = self.user_themes_dir / f"{theme_def.name}.yaml"
        
        if theme_path.exists() and not overwrite:
            raise FileExistsError(f"Theme '{theme_def.name}' already exists")
        
        # Convert to dictionary for serialization
        theme_dict = theme_def.dict(exclude_unset=True)
        
        # Write YAML file
        try:
            with open(theme_path, 'w', encoding='utf-8') as f:
                yaml.dump(theme_dict, f, default_flow_style=False, indent=2)
            
            # Update registry
            self._user_themes.add(theme_def.name)
            self._theme_cache.pop(theme_def.name, None)  # Clear cache
            
            logger.info(f"Saved user theme: {theme_def.name}")
            
        except Exception as e:
            raise ValueError(f"Error saving theme '{theme_def.name}': {e}")
    
    def delete_user_theme(self, theme_name: str) -> bool:
        """Delete a user theme.
        
        Args:
            theme_name: Name of the theme to delete
            
        Returns:
            True if theme was deleted, False if not found
        """
        yaml_path = self.user_themes_dir / f"{theme_name}.yaml"
        json_path = self.user_themes_dir / f"{theme_name}.json"
        
        deleted = False
        
        if yaml_path.exists():
            yaml_path.unlink()
            deleted = True
            
        if json_path.exists():
            json_path.unlink()
            deleted = True
        
        if deleted:
            self._user_themes.discard(theme_name)
            self._theme_cache.pop(theme_name, None)  # Clear cache
            self._variant_cache.pop(theme_name, None)
            logger.info(f"Deleted user theme: {theme_name}")
        
        return deleted
    
    def load_user_overrides(self, overrides_path: Path) -> UserThemeOverrides:
        """Load user theme overrides from file.
        
        Args:
            overrides_path: Path to user overrides file
            
        Returns:
            UserThemeOverrides instance
            
        Raises:
            FileNotFoundError: If file not found
            ValueError: If overrides are invalid
        """
        if not overrides_path.exists():
            raise FileNotFoundError(f"Overrides file not found: {overrides_path}")
        
        if overrides_path.suffix.lower() == '.yaml' or overrides_path.suffix.lower() == '.yml':
            override_data = self._load_yaml_file(overrides_path)
        elif overrides_path.suffix.lower() == '.json':
            override_data = self._load_json_file(overrides_path)
        else:
            raise ValueError(f"Unsupported file format: {overrides_path.suffix}")
        
        try:
            return UserThemeOverrides(**override_data)
        except Exception as e:
            raise ValueError(f"Invalid user overrides: {e}")
    
    def validate_theme(self, theme_name: str) -> List[str]:
        """Validate a theme definition and return any issues.
        
        Args:
            theme_name: Name of the theme to validate
            
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        try:
            theme_def = self.load_theme_definition(theme_name)
            
            # Validate palette colors
            palette_dict = theme_def.palette.dict()
            from .utils import validate_color_accessibility
            accessibility_issues = validate_color_accessibility(palette_dict)
            issues.extend(accessibility_issues)
            
            # Check for circular inheritance
            if theme_def.extends:
                visited = {theme_name}
                current = theme_def.extends
                while current and current not in visited:
                    visited.add(current)
                    try:
                        parent = self.load_theme_definition(current)
                        current = parent.extends
                    except Exception:
                        issues.append(f"Extended theme '{current}' not found")
                        break
                
                if current and current in visited:
                    issues.append(f"Circular inheritance detected: {' -> '.join(visited)} -> {current}")
            
            # Validate variants
            for variant in theme_def.variants:
                if not variant.name:
                    issues.append("Variant missing name")
        
        except Exception as e:
            issues.append(f"Failed to load theme: {e}")
        
        return issues
    
    def clear_cache(self) -> None:
        """Clear the theme cache and rescan."""
        self._theme_cache.clear()
        self._variant_cache.clear()
        self._scan_builtin_themes()
        self._scan_user_themes()
    
    def get_theme_info(self, theme_name: str) -> Dict[str, Any]:
        """Get detailed information about a theme.
        
        Args:
            theme_name: Name of the theme
            
        Returns:
            Theme information dictionary
        """
        try:
            theme_def = self.load_theme_definition(theme_name)
            
            info = {
                'name': theme_def.name,
                'display_name': theme_def.display_name,
                'description': theme_def.description,
                'version': theme_def.version,
                'author': theme_def.author,
                'extends': theme_def.extends,
                'min_capability': theme_def.min_capability.value,
                'variants': [
                    {
                        'name': v.name,
                        'description': v.description,
                        'high_contrast': v.high_contrast,
                        'colorblind_safe': v.colorblind_safe,
                        'compact': v.compact,
                        'minimal': v.minimal
                    } for v in theme_def.variants
                ],
                'palette': theme_def.palette.dict(),
                'effects': {
                    'animations_enabled': theme_def.effects.animations_enabled,
                    'spinner_style': theme_def.effects.spinner_style
                },
                'type': 'builtin' if theme_name in self._builtin_themes else 'user',
                'validation_issues': self.validate_theme(theme_name)
            }
            
            return info
            
        except Exception as e:
            return {
                'name': theme_name,
                'error': str(e),
                'type': 'builtin' if theme_name in self._builtin_themes else 'user'
            }
    
    @lru_cache(maxsize=32)
    def get_default_theme_name(self) -> str:
        """Get the name of the default theme.
        
        Returns:
            Name of the default theme ('city_lights' or first available)
        """
        if 'city_lights' in self._builtin_themes:
            return 'city_lights'
        elif self._builtin_themes:
            return next(iter(sorted(self._builtin_themes)))
        else:
            # Fallback if no themes available
            return 'default'