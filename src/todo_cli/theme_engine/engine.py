"""Core theme engine for the Todo CLI theming system.

This module provides the ThemeEngine class that compiles themes, manages
inheritance and variants, handles terminal capability detection, and provides
Rich console integration with caching for performance.
"""

import re
from typing import Dict, Optional, Any, Tuple, List
from pathlib import Path
from functools import lru_cache
import logging

from rich.console import Console
from rich.theme import Theme as RichTheme

from .schema import (
    ThemeDefinition,
    ThemeVariant,
    CompiledTheme,
    UserThemeOverrides,
    TerminalCapability,
    IconPack
)
from .registry import ThemeRegistry
from .utils import (
    detect_terminal_capability,
    deep_merge_dict,
    parse_rich_style,
    build_rich_style,
    downgrade_color,
    generate_colorblind_safe_palette,
    get_console_dimensions,
    get_responsive_breakpoint
)

logger = logging.getLogger(__name__)


class ThemeEngine:
    """Core theme engine for compiling and applying themes."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the theme engine.
        
        Args:
            config_dir: Optional custom config directory path
        """
        self.registry = ThemeRegistry(config_dir)
        
        # Terminal capability detection
        self.terminal_capability = detect_terminal_capability()
        
        # Compiled theme cache (theme_key -> compiled_theme)
        self._compiled_cache: Dict[str, CompiledTheme] = {}
        self._console_cache: Dict[str, Console] = {}
        
        logger.debug(f"ThemeEngine initialized with capability: {self.terminal_capability}")
    
    @classmethod
    def from_config(cls, config) -> 'ThemeEngine':
        """Create theme engine from application config.
        
        Args:
            config: Application configuration object
            
        Returns:
            ThemeEngine instance
        """
        config_dir = Path(config.data_dir) if hasattr(config, 'data_dir') else None
        return cls(config_dir)
    
    @classmethod
    def from_name(cls, theme_name: str, variant: Optional[str] = None, 
                  config_dir: Optional[Path] = None) -> 'ThemeEngine':
        """Create theme engine with a specific theme loaded.
        
        Args:
            theme_name: Name of theme to load
            variant: Optional variant name
            config_dir: Optional config directory
            
        Returns:
            ThemeEngine instance
        """
        engine = cls(config_dir)
        engine.load_theme(theme_name, variant)
        return engine
    
    def load_theme(self, theme_name: str, variant: Optional[str] = None,
                   user_overrides: Optional[UserThemeOverrides] = None,
                   **runtime_flags) -> CompiledTheme:
        """Load and compile a theme.
        
        Args:
            theme_name: Name of the theme to load
            variant: Optional variant name
            user_overrides: Optional user customization overrides
            **runtime_flags: Runtime theme flags (compact, minimal, etc.)
            
        Returns:
            CompiledTheme instance
            
        Raises:
            ValueError: If theme cannot be loaded or compiled
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                theme_name, variant, user_overrides, runtime_flags
            )
            
            # Check cache first
            if cache_key in self._compiled_cache:
                return self._compiled_cache[cache_key]
            
            # Load base theme definition
            theme_def = self.registry.load_theme_definition(theme_name)
            
            # Apply variant if specified
            variant_obj = None
            if variant:
                variant_obj = self._find_variant(theme_def, variant)
                if variant_obj:
                    theme_def = self._apply_variant(theme_def, variant_obj)
                else:
                    logger.warning(f"Variant '{variant}' not found for theme '{theme_name}'")
            
            # Apply user overrides if provided
            if user_overrides:
                theme_def = self._apply_user_overrides(theme_def, user_overrides)
            
            # Apply runtime flags
            theme_def = self._apply_runtime_flags(theme_def, runtime_flags)
            
            # Compile the theme
            compiled_theme = self._compile_theme(theme_def, variant_obj, runtime_flags)
            
            # Cache the result
            self._compiled_cache[cache_key] = compiled_theme
            
            logger.debug(f"Compiled theme '{theme_name}' with variant '{variant}'")
            return compiled_theme
            
        except Exception as e:
            logger.error(f"Error loading theme '{theme_name}': {e}")
            raise ValueError(f"Failed to load theme '{theme_name}': {e}")
    
    def get_console(self, theme_name: Optional[str] = None, 
                    variant: Optional[str] = None,
                    **runtime_flags) -> Console:
        """Get a Rich Console instance with the specified theme applied.
        
        Args:
            theme_name: Optional theme name (uses default if not specified)
            variant: Optional variant name
            **runtime_flags: Runtime theme flags
            
        Returns:
            Rich Console instance with theme applied
        """
        # Use default theme if none specified
        if not theme_name:
            theme_name = self.registry.get_default_theme_name()
        
        # Generate cache key
        cache_key = self._generate_cache_key(theme_name, variant, None, runtime_flags)
        console_key = f"console_{cache_key}"
        
        # Check console cache
        if console_key in self._console_cache:
            return self._console_cache[console_key]
        
        # Load and compile theme
        compiled_theme = self.load_theme(theme_name, variant, **runtime_flags)
        
        # Create Rich theme from compiled tokens
        rich_theme = RichTheme(compiled_theme.rich_theme_dict)
        
        # Create console with theme
        console = Console(
            theme=rich_theme,
            color_system=self._get_color_system(),
            force_terminal=None,  # Let Rich auto-detect
            width=None,  # Auto-detect width
            height=None  # Auto-detect height
        )
        
        # Cache the console
        self._console_cache[console_key] = console
        
        return console
    
    def compile_rich_theme(self, theme_name: Optional[str] = None,
                          variant: Optional[str] = None,
                          **runtime_flags) -> RichTheme:
        """Compile a theme into a Rich Theme object.
        
        Args:
            theme_name: Optional theme name
            variant: Optional variant name  
            **runtime_flags: Runtime theme flags
            
        Returns:
            Rich Theme object
        """
        if not theme_name:
            theme_name = self.registry.get_default_theme_name()
            
        compiled_theme = self.load_theme(theme_name, variant, **runtime_flags)
        return RichTheme(compiled_theme.rich_theme_dict)
    
    def get_theme_tokens(self, theme_name: Optional[str] = None,
                        variant: Optional[str] = None,
                        **runtime_flags) -> Dict[str, str]:
        """Get resolved theme tokens for use in custom styling.
        
        Args:
            theme_name: Optional theme name
            variant: Optional variant name
            **runtime_flags: Runtime theme flags
            
        Returns:
            Dictionary of resolved theme tokens
        """
        if not theme_name:
            theme_name = self.registry.get_default_theme_name()
            
        compiled_theme = self.load_theme(theme_name, variant, **runtime_flags)
        
        # Combine semantic and component tokens
        all_tokens = {}
        all_tokens.update(compiled_theme.resolved_semantic)
        all_tokens.update(compiled_theme.resolved_components)
        
        return all_tokens
    
    def get_icon_set(self, theme_name: Optional[str] = None,
                    icon_pack: IconPack = IconPack.DEFAULT) -> Dict[str, str]:
        """Get icon set from theme with fallbacks.
        
        Args:
            theme_name: Optional theme name
            icon_pack: Icon pack to use
            
        Returns:
            Dictionary of icon mappings
        """
        if not theme_name:
            theme_name = self.registry.get_default_theme_name()
            
        try:
            theme_def = self.registry.load_theme_definition(theme_name)
            icons = theme_def.icons.dict()
            
            # Apply icon pack preference
            if icon_pack == IconPack.ASCII_ONLY:
                # Use ASCII fallbacks
                ascii_icons = {k: v for k, v in icons.items() if k.startswith('ascii_')}
                # Map ascii_* keys to their base names
                for key, value in ascii_icons.items():
                    base_key = key.replace('ascii_', '')
                    if base_key in icons:
                        icons[base_key] = value
            
            return icons
            
        except Exception as e:
            logger.error(f"Error loading icon set: {e}")
            # Return safe fallback icons
            return {
                'pending': '[ ]',
                'completed': '[x]',
                'pinned': '[*]',
                'critical': '[!]',
                'high': '[H]',
                'medium': '[M]',
                'low': '[L]'
            }
    
    def get_responsive_layout(self, console: Console, theme_name: Optional[str] = None) -> str:
        """Get responsive layout breakpoint for the given console.
        
        Args:
            console: Rich Console instance
            theme_name: Optional theme name
            
        Returns:
            Responsive breakpoint ('xs', 'sm', 'md', 'lg')
        """
        width, height = get_console_dimensions(console)
        return get_responsive_breakpoint(width)
    
    def clear_cache(self) -> None:
        """Clear all theme and console caches."""
        self._compiled_cache.clear()
        self._console_cache.clear()
        self.registry.clear_cache()
        logger.debug("Theme engine cache cleared")
    
    def _generate_cache_key(self, theme_name: str, variant: Optional[str],
                           user_overrides: Optional[UserThemeOverrides],
                           runtime_flags: Dict[str, Any]) -> str:
        """Generate cache key for theme compilation."""
        key_parts = [
            theme_name,
            variant or 'default',
            self.terminal_capability.value,
            str(hash(str(sorted(runtime_flags.items())))),
        ]
        
        if user_overrides:
            # Include hash of user overrides
            overrides_hash = hash(str(sorted(user_overrides.dict().items())))
            key_parts.append(str(overrides_hash))
        
        return '_'.join(key_parts)
    
    def _find_variant(self, theme_def: ThemeDefinition, variant_name: str) -> Optional[ThemeVariant]:
        """Find a variant by name in the theme definition."""
        for variant in theme_def.variants:
            if variant.name == variant_name:
                return variant
        return None
    
    def _apply_variant(self, theme_def: ThemeDefinition, variant: ThemeVariant) -> ThemeDefinition:
        """Apply variant overrides to theme definition."""
        # Convert to dictionary for merging
        theme_dict = theme_def.dict()
        
        # Apply palette overrides
        if variant.palette_overrides:
            if 'palette' not in theme_dict:
                theme_dict['palette'] = {}
            theme_dict['palette'].update(variant.palette_overrides)
        
        # Apply semantic token overrides
        if variant.semantic_overrides:
            if 'semantic' not in theme_dict:
                theme_dict['semantic'] = {}
            theme_dict['semantic'].update(variant.semantic_overrides)
        
        # Apply component token overrides
        if variant.component_overrides:
            if 'components' not in theme_dict:
                theme_dict['components'] = {}
            theme_dict['components'].update(variant.component_overrides)
        
        # Apply layout overrides
        if variant.layout_overrides:
            if 'layout' not in theme_dict:
                theme_dict['layout'] = {}
            theme_dict['layout'] = deep_merge_dict(theme_dict['layout'], variant.layout_overrides)
        
        # Apply icon overrides
        if variant.icon_overrides:
            if 'icons' not in theme_dict:
                theme_dict['icons'] = {}
            theme_dict['icons'].update(variant.icon_overrides)
        
        return ThemeDefinition(**theme_dict)
    
    def _apply_user_overrides(self, theme_def: ThemeDefinition, 
                             overrides: UserThemeOverrides) -> ThemeDefinition:
        """Apply user customization overrides to theme definition."""
        theme_dict = theme_def.dict()
        
        # Apply each type of override
        override_mappings = [
            ('palette', overrides.palette),
            ('semantic', overrides.semantic),
            ('components', overrides.components),
            ('typography', overrides.typography),
            ('layout', overrides.layout),
            ('icons', overrides.icons),
            ('effects', overrides.effects),
            ('ascii_art', overrides.ascii_art),
        ]
        
        for key, override_data in override_mappings:
            if override_data:
                if key not in theme_dict:
                    theme_dict[key] = {}
                
                if isinstance(override_data, dict):
                    if isinstance(theme_dict[key], dict):
                        theme_dict[key] = deep_merge_dict(theme_dict[key], override_data)
                    else:
                        theme_dict[key] = override_data
                else:
                    theme_dict[key] = override_data
        
        return ThemeDefinition(**theme_dict)
    
    def _apply_runtime_flags(self, theme_def: ThemeDefinition, 
                           runtime_flags: Dict[str, Any]) -> ThemeDefinition:
        """Apply runtime flags to theme definition."""
        theme_dict = theme_def.dict()
        
        # Handle colorblind safe mode
        if runtime_flags.get('colorblind_safe'):
            palette_dict = theme_dict.get('palette', {})
            safe_palette = generate_colorblind_safe_palette(palette_dict)
            theme_dict['palette'] = safe_palette
        
        # Handle high contrast mode  
        if runtime_flags.get('high_contrast'):
            # Apply high contrast adjustments
            if 'palette' in theme_dict:
                palette = theme_dict['palette']
                high_contrast_palette = self._create_high_contrast_palette(palette)
                theme_dict['palette'] = high_contrast_palette
        
        # Handle compact mode
        if runtime_flags.get('compact'):
            if 'layout' not in theme_dict:
                theme_dict['layout'] = {}
            theme_dict['layout']['panel_padding'] = (0, 1)
            theme_dict['layout']['section_spacing'] = 0
        
        # Handle minimal mode
        if runtime_flags.get('minimal'):
            if 'layout' not in theme_dict:
                theme_dict['layout'] = {}
            theme_dict['layout']['panel_padding'] = (0, 0)
            theme_dict['layout']['section_spacing'] = 0
            theme_dict['layout']['item_spacing'] = 0
        
        return ThemeDefinition(**theme_dict)
    
    def _create_high_contrast_palette(self, palette: Dict[str, Any]) -> Dict[str, Any]:
        """Create a high-contrast version of a color palette."""
        from .utils import hex_to_rgb, rgb_to_hex, calculate_contrast_ratio
        
        high_contrast_palette = palette.copy()
        
        # Key contrast pairs to optimize
        contrast_pairs = [
            ('text_primary', 'background'),
            ('text_secondary', 'background'),
            ('success', 'background'),
            ('warning', 'background'),
            ('error', 'background'),
            ('critical', 'background'),
        ]
        
        for fg_key, bg_key in contrast_pairs:
            if fg_key in palette and bg_key in palette:
                fg_color = palette[fg_key]
                bg_color = palette[bg_key]
                
                try:
                    # Check if colors are hex format
                    if fg_color.startswith('#') and bg_color.startswith('#'):
                        current_ratio = calculate_contrast_ratio(fg_color, bg_color)
                        
                        # If contrast is too low, enhance it
                        if current_ratio < 7.0:  # WCAG AAA standard
                            enhanced_fg = self._enhance_contrast_color(fg_color, bg_color, True)
                            high_contrast_palette[fg_key] = enhanced_fg
                except (ValueError, AttributeError):
                    # Skip if color format is not supported
                    continue
        
        # Make background more extreme (pure black or white)
        if 'background' in palette:
            bg_color = palette['background']
            if bg_color.startswith('#'):
                try:
                    r, g, b = hex_to_rgb(bg_color)
                    luminance = (r + g + b) / 3
                    # Make it pure black or white based on current luminance
                    high_contrast_palette['background'] = '#000000' if luminance < 128 else '#FFFFFF'
                except (ValueError, AttributeError):
                    pass
        
        return high_contrast_palette
    
    def _enhance_contrast_color(self, fg_color: str, bg_color: str, is_foreground: bool) -> str:
        """Enhance a color to increase contrast against a background."""
        from .utils import hex_to_rgb, rgb_to_hex
        
        try:
            fg_r, fg_g, fg_b = hex_to_rgb(fg_color)
            bg_r, bg_g, bg_b = hex_to_rgb(bg_color)
            
            # Calculate background luminance
            bg_luminance = (bg_r + bg_g + bg_b) / 3
            
            if is_foreground:
                if bg_luminance < 128:  # Dark background
                    # Make foreground brighter
                    factor = 1.5
                    new_r = min(255, int(fg_r * factor))
                    new_g = min(255, int(fg_g * factor))
                    new_b = min(255, int(fg_b * factor))
                else:  # Light background
                    # Make foreground darker
                    factor = 0.6
                    new_r = max(0, int(fg_r * factor))
                    new_g = max(0, int(fg_g * factor))
                    new_b = max(0, int(fg_b * factor))
                
                return rgb_to_hex((new_r, new_g, new_b))
            
        except (ValueError, AttributeError):
            # Return original color if enhancement fails
            pass
        
        return fg_color
    
    def _compile_theme(self, theme_def: ThemeDefinition,
                      variant: Optional[ThemeVariant],
                      runtime_flags: Dict[str, Any]) -> CompiledTheme:
        """Compile theme definition into executable format."""
        
        # Get palette as dictionary
        palette_dict = theme_def.palette.dict()
        
        # Resolve semantic tokens
        resolved_semantic = {}
        for token_name, token_value in theme_def.semantic.dict().items():
            resolved_semantic[token_name] = self._resolve_token(token_value, palette_dict)
        
        # Resolve component tokens
        resolved_components = {}
        for token_name, token_value in theme_def.components.dict().items():
            resolved_components[token_name] = self._resolve_token(token_value, palette_dict)
        
        # Build Rich theme dictionary
        rich_theme_dict = {}
        rich_theme_dict.update(resolved_semantic)
        rich_theme_dict.update(resolved_components)
        
        # Add background support if theme specifies it
        if 'background' in palette_dict:
            rich_theme_dict['app_bg'] = f"on_{palette_dict['background']}"
            rich_theme_dict['panel_bg'] = f"on_{palette_dict.get('surface', palette_dict['background'])}"
            rich_theme_dict['table_bg'] = f"on_{palette_dict.get('surface_light', palette_dict['background'])}"
        
        # Downgrade colors for terminal capability
        for key, style in rich_theme_dict.items():
            rich_theme_dict[key] = self._adapt_style_for_capability(style)
        
        # Create compiled theme
        compiled_theme = CompiledTheme(
            definition=theme_def,
            variant=variant,
            capability=self.terminal_capability,
            resolved_semantic=resolved_semantic,
            resolved_components=resolved_components,
            rich_theme_dict=rich_theme_dict,
            compact=runtime_flags.get('compact', False),
            minimal=runtime_flags.get('minimal', False),
            animations_enabled=runtime_flags.get('animations_enabled', True),
            icon_pack=runtime_flags.get('icon_pack', IconPack.DEFAULT)
        )
        
        return compiled_theme
    
    def _resolve_token(self, token_value: str, palette: Dict[str, str]) -> str:
        """Resolve a token value by substituting palette color names."""
        resolved = token_value
        
        # Replace palette color references
        for color_name, color_value in palette.items():
            # Match whole words only
            pattern = r'\b' + re.escape(color_name) + r'\b'
            resolved = re.sub(pattern, color_value, resolved)
        
        return resolved
    
    def _adapt_style_for_capability(self, style: str) -> str:
        """Adapt a style string for the current terminal capability."""
        if self.terminal_capability == TerminalCapability.TRUECOLOR:
            return style
        
        # Parse style components
        components = parse_rich_style(style)
        
        # Build adapted style
        return build_rich_style(components, self.terminal_capability)
    
    def _get_color_system(self) -> Optional[str]:
        """Get the color system string for Rich Console."""
        mapping = {
            TerminalCapability.TRUECOLOR: "truecolor",
            TerminalCapability.COLOR_256: "256",
            TerminalCapability.COLOR_16: "standard",
            TerminalCapability.MONOCHROME: None
        }
        return mapping.get(self.terminal_capability)
    
    # Public API for theme management
    def list_themes(self) -> List[Dict[str, Any]]:
        """List all available themes."""
        return self.registry.list_available_themes()
    
    def theme_exists(self, theme_name: str) -> bool:
        """Check if a theme exists."""
        return self.registry.theme_exists(theme_name)
    
    def get_theme_info(self, theme_name: str) -> Dict[str, Any]:
        """Get detailed theme information."""
        return self.registry.get_theme_info(theme_name)
    
    def validate_theme(self, theme_name: str) -> List[str]:
        """Validate a theme and return issues."""
        return self.registry.validate_theme(theme_name)