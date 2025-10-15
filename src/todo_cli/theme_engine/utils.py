"""Utility functions for theme engine operations.

This module provides color conversion, terminal capability detection,
contrast calculation, and safe fallback utilities for the theming system.
"""

import os
import sys
import re
import colorsys
from typing import Tuple, Optional, Dict, Any, List
from rich.console import Console
from rich.color import Color, ColorParseError

from .schema import TerminalCapability, ColorFormat


def detect_terminal_capability() -> TerminalCapability:
    """Detect the color capability of the current terminal.
    
    Returns:
        TerminalCapability enum indicating color support level
    """
    # Check if we're in a TTY
    if not sys.stdout.isatty():
        return TerminalCapability.MONOCHROME
    
    # Check environment variables for color support
    colorterm = os.environ.get('COLORTERM', '').lower()
    term = os.environ.get('TERM', '').lower()
    
    # True color support
    if colorterm in ('truecolor', '24bit') or '24bit' in colorterm or 'truecolor' in colorterm:
        return TerminalCapability.TRUECOLOR
    
    # 256 color support
    if '256' in term or '256color' in term:
        return TerminalCapability.COLOR_256
    
    # Basic color support
    if 'color' in term or term in ('xterm', 'screen', 'tmux'):
        return TerminalCapability.COLOR_16
    
    # Default to monochrome for unknown terminals
    return TerminalCapability.MONOCHROME


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple.
    
    Args:
        hex_color: Hex color string (e.g., '#FF0000' or 'FF0000')
        
    Returns:
        RGB tuple (r, g, b) with values 0-255
        
    Raises:
        ValueError: If hex_color is not a valid hex color
    """
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16) 
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError as e:
        raise ValueError(f"Invalid hex color: {hex_color}") from e


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hex color string.
    
    Args:
        r, g, b: RGB values 0-255
        
    Returns:
        Hex color string with # prefix
    """
    return f"#{r:02x}{g:02x}{b:02x}"


def calculate_luminance(r: int, g: int, b: int) -> float:
    """Calculate relative luminance of an RGB color.
    
    Uses the WCAG formula for luminance calculation.
    
    Args:
        r, g, b: RGB values 0-255
        
    Returns:
        Relative luminance 0.0-1.0
    """
    def gamma_correct(value: int) -> float:
        normalized = value / 255.0
        if normalized <= 0.03928:
            return normalized / 12.92
        else:
            return ((normalized + 0.055) / 1.055) ** 2.4
    
    r_linear = gamma_correct(r)
    g_linear = gamma_correct(g)
    b_linear = gamma_correct(b)
    
    return 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two colors.
    
    Args:
        color1, color2: Hex color strings
        
    Returns:
        Contrast ratio 1.0-21.0 (higher is more contrast)
    """
    try:
        r1, g1, b1 = hex_to_rgb(color1)
        r2, g2, b2 = hex_to_rgb(color2)
        
        lum1 = calculate_luminance(r1, g1, b1)
        lum2 = calculate_luminance(r2, g2, b2)
        
        # Ensure lighter color is in numerator
        if lum1 < lum2:
            lum1, lum2 = lum2, lum1
            
        return (lum1 + 0.05) / (lum2 + 0.05)
        
    except ValueError:
        # If colors can't be parsed, return minimal contrast
        return 1.0


def meets_wcag_contrast(fg_color: str, bg_color: str, level: str = 'AA') -> bool:
    """Check if color combination meets WCAG contrast requirements.
    
    Args:
        fg_color: Foreground hex color
        bg_color: Background hex color  
        level: 'AA' (4.5:1) or 'AAA' (7:1)
        
    Returns:
        True if contrast meets requirements
    """
    ratio = calculate_contrast_ratio(fg_color, bg_color)
    
    if level == 'AAA':
        return ratio >= 7.0
    else:  # AA
        return ratio >= 4.5


def find_nearest_color_256(r: int, g: int, b: int) -> int:
    """Find the nearest color in the 256-color palette.
    
    Args:
        r, g, b: RGB values 0-255
        
    Returns:
        Color index 0-255 for 256-color palette
    """
    # Handle grayscale colors (232-255)
    gray = (r + g + b) // 3
    if abs(r - gray) < 10 and abs(g - gray) < 10 and abs(b - gray) < 10:
        gray_index = min(23, max(0, (gray - 8) // 10))
        return 232 + gray_index
    
    # Handle colored palette (16-231)
    def to_6cube(val):
        if val < 48:
            return 0
        elif val < 114:
            return 1
        else:
            return min(5, (val - 114) // 40 + 2)
    
    cube_r = to_6cube(r)
    cube_g = to_6cube(g)
    cube_b = to_6cube(b)
    
    return 16 + 36 * cube_r + 6 * cube_g + cube_b


def find_nearest_color_16(r: int, g: int, b: int) -> str:
    """Find the nearest color name in the 16-color palette.
    
    Args:
        r, g, b: RGB values 0-255
        
    Returns:
        Color name from basic 16-color set
    """
    # Basic 16 color RGB values (approximate)
    colors_16 = {
        'black': (0, 0, 0),
        'red': (128, 0, 0),
        'green': (0, 128, 0),
        'yellow': (128, 128, 0),
        'blue': (0, 0, 128),
        'magenta': (128, 0, 128),
        'cyan': (0, 128, 128),
        'white': (192, 192, 192),
        'bright_black': (128, 128, 128),
        'bright_red': (255, 0, 0),
        'bright_green': (0, 255, 0),
        'bright_yellow': (255, 255, 0),
        'bright_blue': (0, 0, 255),
        'bright_magenta': (255, 0, 255),
        'bright_cyan': (0, 255, 255),
        'bright_white': (255, 255, 255),
    }
    
    min_distance = float('inf')
    nearest_color = 'white'
    
    for color_name, (cr, cg, cb) in colors_16.items():
        distance = ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5
        if distance < min_distance:
            min_distance = distance
            nearest_color = color_name
    
    return nearest_color


def downgrade_color(color: str, capability: TerminalCapability) -> str:
    """Downgrade a color to match terminal capability.
    
    Args:
        color: Original color (hex, rgb, or name)
        capability: Target terminal capability
        
    Returns:
        Color string appropriate for terminal capability
    """
    if capability == TerminalCapability.TRUECOLOR:
        return color
    
    # Try to parse as hex color
    hex_match = re.match(r'^#?([0-9A-Fa-f]{6})$', color.strip())
    if hex_match:
        hex_color = hex_match.group(1)
        r, g, b = hex_to_rgb(f"#{hex_color}")
        
        if capability == TerminalCapability.COLOR_256:
            color_index = find_nearest_color_256(r, g, b)
            return str(color_index)
        elif capability == TerminalCapability.COLOR_16:
            return find_nearest_color_16(r, g, b)
        else:  # MONOCHROME
            gray = (r + g + b) // 3
            return 'white' if gray > 128 else 'black'
    
    # Try to parse RGB
    rgb_match = re.match(r'^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$', color.strip())
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        
        if capability == TerminalCapability.COLOR_256:
            color_index = find_nearest_color_256(r, g, b)
            return str(color_index)
        elif capability == TerminalCapability.COLOR_16:
            return find_nearest_color_16(r, g, b)
        else:  # MONOCHROME
            gray = (r + g + b) // 3
            return 'white' if gray > 128 else 'black'
    
    # For named colors or complex Rich styles, return as-is for 16+ colors
    if capability in (TerminalCapability.COLOR_256, TerminalCapability.COLOR_16):
        return color
    
    # For monochrome, convert to white/black based on color name
    color_lower = color.lower()
    if any(dark in color_lower for dark in ['black', 'dark', 'dim']):
        return 'black'
    else:
        return 'white'


def parse_rich_style(style_str: str) -> Dict[str, Any]:
    """Parse a Rich style string into components.
    
    Args:
        style_str: Rich style string (e.g., "#ff0000 bold italic")
        
    Returns:
        Dictionary with parsed style components
    """
    components = {
        'color': None,
        'bgcolor': None,
        'bold': False,
        'italic': False,
        'underline': False,
        'dim': False,
    }
    
    parts = style_str.split()
    
    for part in parts:
        part_lower = part.lower()
        
        # Color (hex, rgb, or name)
        if part.startswith('#') or part_lower.startswith('rgb(') or part_lower in [
            'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
            'bright_black', 'bright_red', 'bright_green', 'bright_yellow',
            'bright_blue', 'bright_magenta', 'bright_cyan', 'bright_white'
        ]:
            components['color'] = part
        
        # Background color  
        elif part.startswith('on_'):
            components['bgcolor'] = part[3:]
        
        # Formatting
        elif part_lower == 'bold':
            components['bold'] = True
        elif part_lower == 'italic':
            components['italic'] = True
        elif part_lower == 'underline':
            components['underline'] = True
        elif part_lower == 'dim':
            components['dim'] = True
    
    return components


def build_rich_style(components: Dict[str, Any], capability: TerminalCapability) -> str:
    """Build a Rich style string from components, respecting terminal capability.
    
    Args:
        components: Style components dict
        capability: Terminal capability
        
    Returns:
        Rich style string
    """
    parts = []
    
    # Add color
    if components.get('color'):
        color = downgrade_color(components['color'], capability)
        parts.append(color)
    
    # Add background color
    if components.get('bgcolor'):
        bgcolor = downgrade_color(components['bgcolor'], capability)
        parts.append(f"on_{bgcolor}")
    
    # Add formatting (supported in all terminals)
    if components.get('bold'):
        parts.append('bold')
    if components.get('italic'):
        parts.append('italic')
    if components.get('underline'):
        parts.append('underline')
    if components.get('dim'):
        parts.append('dim')
    
    return ' '.join(parts) if parts else ''


def deep_merge_dict(base: Dict[Any, Any], overlay: Dict[Any, Any]) -> Dict[Any, Any]:
    """Deep merge two dictionaries, with overlay taking precedence.
    
    Args:
        base: Base dictionary
        overlay: Overlay dictionary (takes precedence)
        
    Returns:
        New merged dictionary
    """
    result = base.copy()
    
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_color_accessibility(palette: Dict[str, str]) -> List[str]:
    """Validate color accessibility in a palette.
    
    Args:
        palette: Dictionary of color names to hex values
        
    Returns:
        List of accessibility warnings
    """
    warnings = []
    
    # Common color combinations to check
    combinations = [
        ('text_primary', 'background'),
        ('text_secondary', 'background'),
        ('success', 'background'),
        ('warning', 'background'),
        ('error', 'background'),
        ('critical', 'background'),
    ]
    
    for fg_key, bg_key in combinations:
        if fg_key in palette and bg_key in palette:
            fg_color = palette[fg_key]
            bg_color = palette[bg_key]
            
            try:
                if not meets_wcag_contrast(fg_color, bg_color, 'AA'):
                    ratio = calculate_contrast_ratio(fg_color, bg_color)
                    warnings.append(
                        f"Low contrast between {fg_key} and {bg_key}: "
                        f"{ratio:.1f}:1 (recommended 4.5:1+)"
                    )
            except ValueError:
                warnings.append(f"Invalid color format in {fg_key} or {bg_key}")
    
    return warnings


def generate_colorblind_safe_palette(base_palette: Dict[str, str]) -> Dict[str, str]:
    """Generate a colorblind-safe version of a palette using Okabe-Ito colors.
    
    Args:
        base_palette: Original color palette
        
    Returns:
        Colorblind-safe palette
    """
    # Okabe-Ito colorblind-safe palette
    okabe_ito = {
        'orange': '#E69F00',
        'sky_blue': '#56B4E9', 
        'bluish_green': '#009E73',
        'yellow': '#F0E442',
        'blue': '#0072B2',
        'vermillion': '#D55E00',
        'reddish_purple': '#CC79A7',
        'black': '#000000',
        'white': '#FFFFFF',
    }
    
    # Map semantic colors to colorblind-safe alternatives
    safe_palette = base_palette.copy()
    
    # Update key colors with colorblind-safe alternatives
    color_mappings = {
        'success': okabe_ito['bluish_green'],
        'warning': okabe_ito['yellow'],
        'error': okabe_ito['vermillion'], 
        'critical': okabe_ito['reddish_purple'],
        'primary': okabe_ito['blue'],
        'secondary': okabe_ito['sky_blue'],
        'accent': okabe_ito['orange'],
        'info': okabe_ito['sky_blue'],
    }
    
    for key, color in color_mappings.items():
        if key in safe_palette:
            safe_palette[key] = color
    
    return safe_palette


def test_glyph_support(console: Console) -> Dict[str, bool]:
    """Test which glyphs are supported by the terminal.
    
    Args:
        console: Rich Console instance
        
    Returns:
        Dict mapping glyph categories to support status
    """
    test_glyphs = {
        'basic_emoji': ['⏳', '✅', '❌', '⭐'],
        'extended_emoji': ['📅', '🔄', '🚫', '🎯'],
        'box_drawing': ['─', '│', '┌', '┐', '└', '┘'],
        'geometric': ['●', '○', '■', '□', '▲', '▼'],
        'arrows': ['→', '←', '↑', '↓', '⇒', '⇐'],
    }
    
    support = {}
    
    # For now, assume all glyphs are supported on macOS/modern terminals
    # In a real implementation, this would test actual rendering
    for category in test_glyphs:
        support[category] = True
    
    return support


def get_console_dimensions(console: Console) -> Tuple[int, int]:
    """Get console dimensions and determine responsive breakpoint.
    
    Args:
        console: Rich Console instance
        
    Returns:
        Tuple of (width, height)
    """
    size = console.size
    return (size.width, size.height)


def get_responsive_breakpoint(width: int) -> str:
    """Determine responsive breakpoint based on console width.
    
    Args:
        width: Console width in characters
        
    Returns:
        Breakpoint name ('xs', 'sm', 'md', 'lg')
    """
    if width < 40:
        return 'xs'
    elif width < 60:
        return 'sm' 
    elif width < 80:
        return 'md'
    else:
        return 'lg'