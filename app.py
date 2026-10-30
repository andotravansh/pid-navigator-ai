"""P&ID Navigator: Streamlit entry point.

Run with:  streamlit run app.py

This file only wires the interface together. Page content lives in
``ui/pages``, engineering logic in ``modules``. Uploads stay in memory for
the session; nothing is saved to disk.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="P&ID Navigator",
    page_icon=":material/account_tree:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.navigation import build_navigation  # noqa: E402  (after set_page_config)
from ui.state import init_state  # noqa: E402
from ui.theme import apply_theme  # noqa: E402


def main() -> None:
    """Initialise state, apply the theme, draw navigation and run the page."""
    init_state()
    apply_theme()
    build_navigation().run()


main()
