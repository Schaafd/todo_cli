"""Todo CLI Theme Engine Package.

This package provides a comprehensive theming system for the Todo CLI with
support for color palettes, semantic tokens, variants, user customizations,
terminal capability detection, and Rich console integration.
"""

from .engine import ThemeEngine
from .registry import ThemeRegistry
from .schema import (
    # Core models
    ThemeDefinition,
    ThemePalette,
    SemanticTokens,
    ComponentTokens,
    CompiledTheme,
    UserThemeOverrides,
    
    # Configuration models
    Typography,
    TypographyPreset,
    LayoutConfig,
    IconSet,
    Effects,
    ASCIIArt,
    ThemeVariant,
    
    # Enums
    TerminalCapability,
    IconPack,
    BorderStyle,
    FontWeight,
    ColorFormat
)
from .utils import (
    detect_terminal_capability,
    hex_to_rgb,
    rgb_to_hex,
    calculate_contrast_ratio,
    meets_wcag_contrast,
    validate_color_accessibility,
    generate_colorblind_safe_palette,
    deep_merge_dict,
    get_responsive_breakpoint
)

__version__ = "1.0.0"

__all__ = [
    # Main classes
    "ThemeEngine",
    "ThemeRegistry", 
    
    # Schema models
    "ThemeDefinition",
    "ThemePalette",
    "SemanticTokens", 
    "ComponentTokens",
    "CompiledTheme",
    "UserThemeOverrides",
    "Typography",
    "TypographyPreset",
    "LayoutConfig",
    "IconSet",
    "Effects",
    "ASCIIArt",
    "ThemeVariant",
    
    # Enums
    "TerminalCapability",
    "IconPack", 
    "BorderStyle",
    "FontWeight",
    "ColorFormat",
    
    # Utilities
    "detect_terminal_capability",
    "hex_to_rgb",
    "rgb_to_hex", 
    "calculate_contrast_ratio",
    "meets_wcag_contrast",
    "validate_color_accessibility",
    "generate_colorblind_safe_palette",
    "deep_merge_dict",
    "get_responsive_breakpoint",
]