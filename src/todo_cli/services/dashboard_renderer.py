"""Rich terminal renderer for dashboard widgets."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.progress_bar import ProgressBar
from rich.layout import Layout
from rich import box
from typing import List, Optional

from .dashboard import (
    Dashboard, Widget, WidgetData, WidgetType, WidgetSize
)


# Size mapping: approximate character widths for each widget size
_SIZE_WIDTH = {
    WidgetSize.SMALL: 28,
    WidgetSize.MEDIUM: 40,
    WidgetSize.LARGE: 60,
    WidgetSize.WIDE: 80,
    WidgetSize.FULL: 120,
}


class WidgetRenderer:
    """Renders individual dashboard widgets using Rich."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    # ------------------------------------------------------------------
    # Type-specific renderers
    # ------------------------------------------------------------------

    def _render_metric(self, widget: Widget, data: WidgetData) -> Panel:
        """Large value with label, unit, and optional trend arrow."""
        value = data.value if data.value is not None else 0
        fmt = data.format or ""
        if fmt:
            try:
                value_str = f"{value:{fmt}}"
            except (ValueError, TypeError):
                value_str = str(value)
        else:
            value_str = str(value)

        unit = data.unit or ""
        trend_str = ""
        if data.trend is not None:
            arrow = "[green]^[/green]" if data.trend >= 0 else "[red]v[/red]"
            trend_str = f"  {arrow} {abs(data.trend):.1f}%"

        color = data.color or "bold cyan"
        icon = data.icon or ""
        icon_prefix = f"{icon} " if icon else ""

        content = Text.from_markup(
            f"{icon_prefix}[{color}]{value_str}{unit}[/{color}]{trend_str}\n"
            f"[dim]{data.label}[/dim]"
        )
        return self._wrap_panel(widget, content)

    def _render_gauge(self, widget: Widget, data: WidgetData) -> Panel:
        """Progress bar with color zones (red/yellow/green)."""
        value = float(data.value) if data.value is not None else 0
        # Determine range – if unit contains /N use that, else assume 0-100
        max_val = 100.0
        if data.unit and data.unit.startswith("/"):
            try:
                max_val = float(data.unit.lstrip("/"))
            except ValueError:
                max_val = 100.0

        pct = min(value / max_val, 1.0) if max_val > 0 else 0
        bar_width = _SIZE_WIDTH.get(widget.size, 40) - 10

        # Color zones
        if pct < 0.33:
            color = "red"
        elif pct < 0.66:
            color = "yellow"
        else:
            color = "green"

        filled = int(pct * bar_width)
        empty = bar_width - filled
        bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"

        fmt = data.format or ".1f"
        try:
            value_str = f"{value:{fmt}}"
        except (ValueError, TypeError):
            value_str = str(value)

        content = Text.from_markup(
            f"[bold]{data.label}[/bold]\n"
            f"{bar}  [{color}]{value_str}{data.unit or ''}[/{color}]"
        )
        return self._wrap_panel(widget, content)

    def _render_sparkline(self, widget: Widget, data: WidgetData) -> Panel:
        """Simple ASCII sparkline chart."""
        chars = "▁▂▃▄▅▆▇█"
        values: List[float] = []
        if data.series:
            values = [float(v) for v in data.series[0].get("data", [])]
        if not values:
            values = [0]

        mn, mx = min(values), max(values)
        rng = mx - mn if mx != mn else 1
        line = "".join(chars[min(int((v - mn) / rng * 7), 7)] for v in values)

        content = Text.from_markup(
            f"[bold]{data.label}[/bold]\n"
            f"[cyan]{line}[/cyan]\n"
            f"[dim]min={mn:.1f}  max={mx:.1f}[/dim]"
        )
        return self._wrap_panel(widget, content)

    def _render_chart_bar(self, widget: Widget, data: WidgetData) -> Panel:
        """Horizontal bar chart."""
        categories = data.categories or []
        values: List[float] = []
        if data.series:
            values = [float(v) for v in data.series[0].get("data", [])]
        if not values:
            values = [0]

        max_val = max(values) if values else 1
        bar_max_w = _SIZE_WIDTH.get(widget.size, 40) - 20
        max_label_len = max((len(str(c)) for c in categories), default=5)

        lines: List[str] = []
        for i, val in enumerate(values):
            label = str(categories[i]) if i < len(categories) else str(i)
            width = int(val / max_val * bar_max_w) if max_val else 0
            bar = "█" * max(width, 1)
            lines.append(f"[dim]{label:>{max_label_len}}[/dim] [cyan]{bar}[/cyan] {val:.1f}")

        content = Text.from_markup(
            f"[bold]{data.label}[/bold]\n" + "\n".join(lines)
        )
        return self._wrap_panel(widget, content)

    def _render_chart_pie(self, widget: Widget, data: WidgetData) -> Panel:
        """Text-based percentage breakdown."""
        categories = data.categories or []
        values: List[float] = []
        if data.series:
            values = [float(v) for v in data.series[0].get("data", [])]
        if not values:
            values = [0]

        total = sum(values) or 1
        colors = ["cyan", "green", "yellow", "magenta", "blue", "red", "white"]

        lines: List[str] = []
        for i, val in enumerate(values):
            label = str(categories[i]) if i < len(categories) else str(i)
            pct = val / total * 100
            color = colors[i % len(colors)]
            block = "█" * max(int(pct / 5), 1)
            lines.append(f"[{color}]{block}[/{color}] {label} ({pct:.1f}%)")

        content = Text.from_markup(
            f"[bold]{data.label}[/bold]\n" + "\n".join(lines)
        )
        return self._wrap_panel(widget, content)

    def _render_table(self, widget: Widget, data: WidgetData) -> Panel:
        """Rich Table inside a panel."""
        table = Table(box=box.SIMPLE, expand=True, show_header=bool(data.headers))
        for hdr in (data.headers or []):
            table.add_column(hdr, style="bold")
        for row in (data.rows or []):
            table.add_row(*(str(c) for c in row))

        return self._wrap_panel(widget, table)

    def _render_list(self, widget: Widget, data: WidgetData) -> Panel:
        """Bulleted list in a Panel."""
        items = data.rows or []
        if not items and data.series:
            items = [[s.get("name", "")] for s in data.series]
        if not items and data.categories:
            items = [[c] for c in data.categories]

        lines = []
        for item in items:
            text = str(item[0]) if isinstance(item, (list, tuple)) and item else str(item)
            lines.append(f"  [cyan]•[/cyan] {text}")

        content = Text.from_markup(
            f"[bold]{data.label}[/bold]\n" + ("\n".join(lines) if lines else "[dim]No items[/dim]")
        )
        return self._wrap_panel(widget, content)

    def _render_text(self, widget: Widget, data: WidgetData) -> Panel:
        """Simple text panel."""
        text = str(data.value) if data.value is not None else data.label or ""
        content = Text.from_markup(text)
        return self._wrap_panel(widget, content)

    def _render_progress_bar(self, widget: Widget, data: WidgetData) -> Panel:
        """Rich ProgressBar."""
        value = float(data.value) if data.value is not None else 0
        max_val = 100.0
        if data.unit and data.unit.startswith("/"):
            try:
                max_val = float(data.unit.lstrip("/"))
            except ValueError:
                max_val = 100.0

        pct = min(value / max_val, 1.0) if max_val > 0 else 0
        bar = ProgressBar(total=max_val, completed=value, width=_SIZE_WIDTH.get(widget.size, 40) - 12)

        # Build a renderable group manually
        fmt = data.format or ".1f"
        try:
            value_str = f"{value:{fmt}}"
        except (ValueError, TypeError):
            value_str = str(value)

        header = Text.from_markup(
            f"[bold]{data.label}[/bold]  [{data.color or 'cyan'}]{value_str}{data.unit or ''}[/{data.color or 'cyan'}]"
        )
        from rich.console import Group
        content = Group(header, bar)
        return self._wrap_panel(widget, content)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wrap_panel(self, widget: Widget, content) -> Panel:
        """Wrap content in a Panel using widget display properties."""
        border = box.ROUNDED if widget.show_border else box.SIMPLE
        title = widget.title if widget.show_title else None
        return Panel(
            content,
            title=title,
            border_style=widget.text_color or "bright_blue",
            style=widget.background_color or "",
            box=border,
            width=_SIZE_WIDTH.get(widget.size, 40),
        )

    # ------------------------------------------------------------------
    # Public dispatch
    # ------------------------------------------------------------------

    _DISPATCH = {
        WidgetType.METRIC: "_render_metric",
        WidgetType.GAUGE: "_render_gauge",
        WidgetType.SPARKLINE: "_render_sparkline",
        WidgetType.CHART_BAR: "_render_chart_bar",
        WidgetType.CHART_PIE: "_render_chart_pie",
        WidgetType.TABLE: "_render_table",
        WidgetType.LIST: "_render_list",
        WidgetType.TEXT: "_render_text",
        WidgetType.PROGRESS_BAR: "_render_progress_bar",
    }

    def render_widget(self, widget: Widget) -> Panel:
        """Render a widget based on its type, falling back to text."""
        data = widget.cached_data or WidgetData(label=widget.title)
        method_name = self._DISPATCH.get(widget.widget_type, "_render_text")
        method = getattr(self, method_name)
        return method(widget, data)


class DashboardRenderer:
    """Renders full dashboards to the terminal."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.widget_renderer = WidgetRenderer(self.console)

    def render(self, dashboard: Dashboard) -> None:
        """Render a complete dashboard."""
        # Title banner
        title_text = Text(dashboard.name, style="bold bright_white")
        if dashboard.description:
            title_text.append(f"  -  {dashboard.description}", style="dim")
        self.console.print(Panel(title_text, border_style="bright_blue", box=box.DOUBLE))

        if not dashboard.widgets:
            self.console.print(
                Panel("[dim]No widgets yet. Use [bold]dashboard add-widget[/bold] to get started.[/dim]",
                      border_style="dim")
            )
            return

        # Group widgets into rows respecting sizes
        panels: List[Panel] = []
        for widget in dashboard.widgets:
            panels.append(self.widget_renderer.render_widget(widget))

        # Use Columns for automatic flow layout
        self.console.print(Columns(panels, equal=False, expand=False))

    def render_dashboard_list(self, dashboards: list) -> None:
        """Render a list of available dashboards as a table."""
        if not dashboards:
            self.console.print("[dim]No dashboards found.[/dim]")
            return

        table = Table(title="Dashboards", box=box.ROUNDED, show_lines=True)
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Name", style="bold cyan")
        table.add_column("Description", style="dim")
        table.add_column("Widgets", justify="right")
        table.add_column("Modified", style="dim")

        for d in dashboards:
            table.add_row(
                d.get("id", "")[:12],
                d.get("name", ""),
                d.get("description", ""),
                str(d.get("widget_count", 0)),
                str(d.get("modified", ""))[:19],
            )

        self.console.print(table)
