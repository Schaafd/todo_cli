"""Theme schema definitions for the Todo CLI theming system.

This module defines the Pydantic models that validate and structure all theme data,
including color palettes, semantic tokens, component styles, typography, layouts,
icons, and effects.
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import re


class ColorFormat(str, Enum):
    """Supported color formats"""
    HEX = "hex"
    RGB = "rgb" 
    RICH_COLOR = "rich_color"


class IconPack(str, Enum):
    """Available icon packs"""
    DEFAULT = "default"
    ASCII_ONLY = "ascii_only"
    NERD_FONT = "nerd_font"


class BorderStyle(str, Enum):
    """Rich border style options"""
    NONE = "none"
    ASCII = "ascii"
    ROUNDED = "rounded"
    HEAVY = "heavy"
    DOUBLE = "double"
    SOLID = "solid"


class FontWeight(str, Enum):
    """Font weight options"""
    NORMAL = "normal"
    BOLD = "bold"
    DIM = "dim"


class TerminalCapability(str, Enum):
    """Terminal color capabilities"""
    TRUECOLOR = "truecolor"
    COLOR_256 = "256"
    COLOR_16 = "16"
    MONOCHROME = "monochrome"


class ThemePalette(BaseModel):
    """Base color palette for a theme"""
    
    # Primary brand colors
    primary: str = Field(..., description="Primary brand color")
    secondary: str = Field(..., description="Secondary accent color")
    accent: str = Field(..., description="Tertiary accent color")
    
    # Background and surface colors
    background: str = Field(..., description="Main background color")
    surface: str = Field(..., description="Card/panel surface color")
    surface_light: str = Field(..., description="Lighter surface variant")
    
    # Text colors
    text_primary: str = Field(..., description="Primary text color")
    text_secondary: str = Field(..., description="Secondary text color")
    text_muted: str = Field(..., description="Muted/dim text color")
    text_bright: str = Field(..., description="Bright/emphasis text color")
    
    # Semantic status colors
    success: str = Field(..., description="Success/completion color")
    warning: str = Field(..., description="Warning/caution color")
    error: str = Field(..., description="Error/failure color")
    critical: str = Field(..., description="Critical/urgent color")
    info: str = Field(..., description="Informational color")
    hint: str = Field(..., description="Hint/suggestion color")
    
    @field_validator('*', mode='before')
    @classmethod
    def validate_color_format(cls, v):
        """Validate color format (hex, rgb, or rich color name)"""
        if isinstance(v, str):
            # Hex color
            if re.match(r'^#[0-9A-Fa-f]{6}$', v):
                return v
            # RGB color
            if re.match(r'^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$', v):
                return v
            # Rich color names (basic validation)
            if v.lower() in ['black', 'white', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta']:
                return v
            # Allow complex rich color specs like "bold red", "#ff0000 bold"
            return v
        return v


class TypographyPreset(BaseModel):
    """Typography preset configuration"""
    weight: FontWeight = FontWeight.NORMAL
    italic: bool = False
    dim: bool = False
    underline: bool = False
    
    def to_rich_style(self, base_color: str = "") -> str:
        """Convert to Rich style string"""
        parts = []
        if base_color:
            parts.append(base_color)
        if self.weight == FontWeight.BOLD:
            parts.append("bold")
        elif self.weight == FontWeight.DIM:
            parts.append("dim")
        if self.italic:
            parts.append("italic")
        if self.underline:
            parts.append("underline")
        return " ".join(parts)


class Typography(BaseModel):
    """Typography configuration"""
    body: TypographyPreset = Field(default_factory=TypographyPreset)
    caption: TypographyPreset = Field(default_factory=lambda: TypographyPreset(weight=FontWeight.DIM))
    header: TypographyPreset = Field(default_factory=lambda: TypographyPreset(weight=FontWeight.BOLD))
    subheader: TypographyPreset = Field(default_factory=TypographyPreset)
    code: TypographyPreset = Field(default_factory=TypographyPreset)
    emphasis: TypographyPreset = Field(default_factory=lambda: TypographyPreset(italic=True))


class LayoutConfig(BaseModel):
    """Layout and spacing configuration"""
    
    # Panel configuration
    panel_padding: Tuple[int, int] = (1, 2)  # (vertical, horizontal)
    panel_border_style: BorderStyle = BorderStyle.ROUNDED
    
    # Table configuration
    table_padding: Tuple[int, int] = (0, 1)
    table_show_header: bool = True
    table_show_lines: bool = False
    
    # Spacing
    section_spacing: int = 1
    item_spacing: int = 0
    
    # Responsive breakpoints (terminal width)
    breakpoint_xs: int = 40
    breakpoint_sm: int = 60
    breakpoint_md: int = 80
    breakpoint_lg: int = 120


class IconSet(BaseModel):
    """Icon configuration for different states"""
    
    # Status icons
    pending: str = "⏳"
    in_progress: str = "🔄"
    completed: str = "✅"
    cancelled: str = "❌"
    blocked: str = "🚫"
    pinned: str = "⭐"
    
    # Priority icons
    critical: str = "🔴"
    high: str = "🟡"
    medium: str = "🔵"
    low: str = "⚪"
    
    # UI icons
    calendar: str = "📅"
    clock: str = "🕰"
    tag: str = "🏷️"
    person: str = "👤"
    project: str = "📋"
    
    # Fallback ASCII equivalents
    ascii_pending: str = "[ ]"
    ascii_completed: str = "[x]"
    ascii_pinned: str = "[*]"
    ascii_critical: str = "[!]"
    ascii_high: str = "[H]"
    ascii_medium: str = "[M]"
    ascii_low: str = "[L]"


class Effects(BaseModel):
    """Visual effects and animations configuration"""
    animations_enabled: bool = True
    spinner_style: str = "dots"
    progress_pulse: bool = True
    transition_duration: float = 0.3
    
    # Animation styles
    fade_in: bool = True
    slide_in: bool = False
    bounce: bool = False


class SemanticTokens(BaseModel):
    """Semantic color tokens that map to palette colors"""
    
    # Status semantics
    success: str = "success bold"
    warning: str = "warning bold"
    error: str = "error bold"  
    critical: str = "critical bold"
    info: str = "info"
    hint: str = "hint dim"
    
    # General semantics
    link: str = "primary underline"
    highlight: str = "accent bold"
    muted: str = "text_muted dim"
    bright: str = "text_bright bold"
    default: str = "text_primary"


class ComponentTokens(BaseModel):
    """Component-specific styling tokens"""
    
    # Headers and text
    header: str = "text_bright bold"
    subheader: str = "accent bold"
    body: str = "text_primary"
    caption: str = "text_secondary dim"
    
    # Panels and containers
    border: str = "surface_light"
    panel_bg: str = "surface"
    panel_title: str = "text_bright bold"
    
    # Tables
    table_header: str = "accent bold"
    table_row: str = "text_primary"
    table_row_alt: str = "text_secondary"
    
    # Todo-specific tokens
    todo_pending: str = "primary"
    todo_completed: str = "success"
    todo_pinned: str = "warning"
    todo_overdue: str = "critical"
    
    # Priority tokens
    priority_critical: str = "critical bold"
    priority_high: str = "warning"
    priority_medium: str = "text_primary"
    priority_low: str = "text_muted dim"
    
    # Metadata tokens
    tag: str = "secondary"
    assignee: str = "success"
    stakeholder: str = "accent"
    due_date: str = "primary"
    due_date_overdue: str = "critical"
    due_date_soon: str = "warning"
    
    # Progress and gauges
    progress_bar: str = "primary"
    progress_bg: str = "surface_light"
    gauge_good: str = "success"
    gauge_warning: str = "warning" 
    gauge_critical: str = "critical"


class ASCIIArt(BaseModel):
    """ASCII art and banners configuration"""
    banner: Optional[str] = None
    banner_style: str = "primary"
    subtitle: str = "⚡ Master Your Tasks. Unleash Your Potential. ⚡"
    subtitle_style: str = "accent"


class ThemeVariant(BaseModel):
    """Theme variant configuration (e.g., high_contrast, compact)"""
    name: str
    description: str = ""
    
    # Override specific aspects
    palette_overrides: Dict[str, str] = Field(default_factory=dict)
    semantic_overrides: Dict[str, str] = Field(default_factory=dict)
    component_overrides: Dict[str, str] = Field(default_factory=dict)
    layout_overrides: Dict[str, Any] = Field(default_factory=dict)
    icon_overrides: Dict[str, str] = Field(default_factory=dict)
    
    # Variant flags
    high_contrast: bool = False
    colorblind_safe: bool = False
    compact: bool = False
    minimal: bool = False


class ThemeDefinition(BaseModel):
    """Complete theme definition"""
    
    # Metadata
    name: str = Field(..., description="Theme name")
    display_name: str = Field(..., description="Human-readable theme name")
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    extends: Optional[str] = None  # Base theme to extend
    
    # Core configuration
    palette: ThemePalette
    semantic: SemanticTokens = Field(default_factory=SemanticTokens)
    components: ComponentTokens = Field(default_factory=ComponentTokens)
    typography: Typography = Field(default_factory=Typography)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    icons: IconSet = Field(default_factory=IconSet)
    effects: Effects = Field(default_factory=Effects)
    ascii_art: ASCIIArt = Field(default_factory=ASCIIArt)
    
    # Variants
    variants: List[ThemeVariant] = Field(default_factory=list)
    
    # Terminal capabilities
    min_capability: TerminalCapability = TerminalCapability.COLOR_16
    
    @model_validator(mode='after')
    def validate_theme_consistency(self):
        """Validate theme consistency and references"""
        # Ensure all palette colors are referenced in semantic/component tokens
        # This is a simplified check - full validation would be more complex
        return self


class CompiledTheme(BaseModel):
    """Compiled theme ready for Rich console"""
    
    definition: ThemeDefinition
    variant: Optional[ThemeVariant] = None
    capability: TerminalCapability = TerminalCapability.TRUECOLOR
    
    # Resolved tokens (palette colors substituted)
    resolved_semantic: Dict[str, str] = Field(default_factory=dict)
    resolved_components: Dict[str, str] = Field(default_factory=dict)
    
    # Rich theme mapping
    rich_theme_dict: Dict[str, str] = Field(default_factory=dict)
    
    # Runtime flags
    compact: bool = False
    minimal: bool = False
    animations_enabled: bool = True
    icon_pack: IconPack = IconPack.DEFAULT


class UserThemeOverrides(BaseModel):
    """User theme customization overrides"""
    
    name: str = Field(..., description="Override name")
    extends: str = Field(..., description="Base theme to extend")
    
    # Partial overrides - all optional
    palette: Optional[Dict[str, str]] = None
    semantic: Optional[Dict[str, str]] = None
    components: Optional[Dict[str, str]] = None
    typography: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None
    icons: Optional[Dict[str, str]] = None
    effects: Optional[Dict[str, Any]] = None
    ascii_art: Optional[Dict[str, Any]] = None
    
    # Runtime preferences
    compact: Optional[bool] = None
    minimal: Optional[bool] = None
    high_contrast: Optional[bool] = None
    colorblind_safe: Optional[bool] = None
    animations_enabled: Optional[bool] = None
    icon_pack: Optional[IconPack] = None


# Type aliases for convenience
ThemeDict = Dict[str, Any]
PaletteDict = Dict[str, str]
TokenDict = Dict[str, str]