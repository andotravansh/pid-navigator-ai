"""Reusable presentation helpers. No engineering logic lives here."""

from __future__ import annotations

import html
from typing import Any, Callable, Optional, Sequence

import streamlit as st
from PIL import Image
from pydantic import ValidationError

from modules.engineering_lists import TableSpec, table_data
from ui import registry
from ui.features import Status

_BADGE_TEXT = {
    Status.IMPLEMENTED: "Implemented",
    Status.EXPERIMENTAL: "Experimental",
    Status.PLANNED: "Planned",
}

# Minimal line icons (24x24 grid, stroke only).
ICONS: dict[str, str] = {
    "brand": '<path d="M12 2l8.5 5v10L12 22l-8.5-5V7z"/><path d="M12 8v8M8.5 10l3.5 2 3.5-2"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8"/>',
    "box": '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3.3 7L12 12l8.7-5M12 22V12"/>',
    "route": '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h8a3 3 0 0 0 0-6H8a3 3 0 0 1 0-6h8"/>',
    "valve": '<path d="M4 6l8 6-8 6zM20 6l-8 6 8 6z"/><path d="M12 12V4"/>',
    "workspace": '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M7 14l3-3 3 3 4-5M8 21h8"/>',
    "lists": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>',
    "ai": '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    "safety": '<path d="M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
    "export": '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    "inbox": '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/>',
    "scan": '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M4 12h16"/>',
    "control": '<path d="M4 6h8M18 6h2M4 12h2M12 12h8M4 18h10M20 18h0"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "calc": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h2M14 12h2M8 16h2M14 16h2"/>',
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def esc(value: Any) -> str:
    """HTML-escape any value (file names and tags are user-controlled)."""
    return html.escape(str(value), quote=True)


def html_block(markup: str) -> None:
    """Render trusted markup (all dynamic parts must go through ``esc``)."""
    st.html("".join(line.strip() for line in markup.strip().splitlines()))


def icon_svg(name: str, size: int = 20) -> str:
    """Inline SVG for a named icon."""
    body = ICONS.get(name, ICONS["file"])
    return (
        f'<span class="pn-ico"><svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
        f'height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{body}</svg></span>'
    )


def badge_html(status: Status, label: Optional[str] = None) -> str:
    """Status pill. Planned items get a dashed outline."""
    return f'<span class="pn-badge pn-{status.value}">{esc(label or _BADGE_TEXT[status])}</span>'


def stretch(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a Streamlit element at full width across Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


def enum_label(value: Any) -> str:
    """Readable label for an enum member."""
    return str(value.value).replace("_", " ").title()


def error_text(exc: Exception) -> str:
    """Short, friendly text for validation or graph errors."""
    if isinstance(exc, ValidationError):
        return "; ".join(str(item["msg"]) for item in exc.errors())
    return str(exc)


def panel(name: str):
    """A styled container. ``name`` must be unique on the page."""
    return st.container(key=f"pn-panel-{name}")


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------
def page_header(
    title: str, subtitle: str, group: str, status: Status, badge_label: Optional[str] = None
) -> None:
    """Breadcrumb, title, status badge and one-line purpose."""
    html_block(
        f"""
<div class="pn-header">
<div class="pn-crumb">P&amp;ID Navigator<i>/</i>{esc(group)}</div>
<div class="pn-title-row"><h1 class="pn-title">{esc(title)}</h1>{badge_html(status, badge_label)}</div>
<p class="pn-sub">{esc(subtitle)}</p>
</div>
"""
    )


def section_heading(
    title: str, caption: Optional[str] = None, status: Optional[Status] = None
) -> None:
    """Heading inside a panel, optionally with a status badge."""
    badge = badge_html(status) if status else ""
    html_block(
        f'<div class="pn-section"><span class="pn-section-title">{esc(title)}</span>{badge}</div>'
    )
    if caption:
        html_block(f'<div class="pn-section-cap">{esc(caption)}</div>')


def metric_card(label: str, value: Any, note: str, icon: str) -> None:
    """Summary number with an honest note about where it comes from."""
    html_block(
        f"""
<div class="pn-card">
<div class="pn-metric-label"><span>{esc(label)}</span>{icon_svg(icon, 18)}</div>
<div class="pn-metric-value">{esc(value)}</div>
<div class="pn-metric-note">{esc(note)}</div>
</div>
"""
    )


def feature_card(
    title: str, text: str, icon: str, status: Status, *, link: bool = False
) -> None:
    """Card describing a module. Planned cards are drawn with a dashed outline."""
    classes = f"pn-card pn-{status.value}" + (" pn-link" if link else "")
    html_block(
        f"""
<div class="{classes}">
<div class="pn-card-head"><span style="display:flex;gap:.55rem;align-items:center">{icon_svg(icon, 20)}<span class="pn-card-title">{esc(title)}</span></span>{badge_html(status)}</div>
<p>{esc(text)}</p>
</div>
"""
    )


def empty_state(title: str, message: str, icon: str = "inbox") -> None:
    """Dashed placeholder explaining what is missing and how to fill it."""
    html_block(
        f"""
<div class="pn-empty">{icon_svg(icon, 26)}
<div class="pn-empty-title">{esc(title)}</div>
<p>{esc(message)}</p>
</div>
"""
    )


def callout(text: str, status: Status, lead: Optional[str] = None) -> None:
    """Short notice whose left rule shows the status (dashed means planned)."""
    lead_html = f"<b>{esc(lead)}</b> " if lead else ""
    html_block(
        f'<div class="pn-callout pn-{status.value}"><div>{lead_html}{esc(text)}</div></div>'
    )


def key_values(pairs: Sequence[tuple[str, Any]]) -> None:
    """Compact label and value rows."""
    rows = "".join(
        f'<div class="pn-kv"><span>{esc(k)}</span><strong>{esc(v)}</strong></div>'
        for k, v in pairs
    )
    html_block(f"<div>{rows}</div>")


def activity_list(entries: Sequence[tuple[str, str]]) -> None:
    """Timestamped log lines (newest first)."""
    rows = "".join(
        f'<div class="pn-log"><time>{esc(t)}</time><span>{esc(m)}</span></div>'
        for t, m in entries
    )
    html_block(f"<div>{rows}</div>")


def schema_table(spec: TableSpec, rows: Sequence[dict[str, Any]] = ()) -> None:
    """Show a table; with no rows only the column headers appear."""
    stretch(st.dataframe, table_data(spec.columns, list(rows)), hide_index=True)


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------
def nav_button(
    key: str,
    label: str,
    *,
    where: str,
    primary: bool = False,
    icon: Optional[str] = None,
) -> None:
    """Button that opens another section (disabled if it is not registered)."""
    page = registry.PAGES.get(key)
    clicked = stretch(
        st.button,
        label,
        key=f"nav_{where}_{key}",
        type="primary" if primary else "secondary",
        icon=icon,
        disabled=page is None,
    )
    if clicked and page is not None:
        st.switch_page(page)


def show_image(image: Image.Image, caption: Optional[str] = None) -> None:
    """Display an image at full column width."""
    stretch(st.image, image, caption=caption)
