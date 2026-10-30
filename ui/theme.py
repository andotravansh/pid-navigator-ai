"""Custom CSS layered on top of .streamlit/config.toml.

Colours, fonts and radii come from the Streamlit theme. This file only
styles our own components and a few stable Streamlit hooks.

Visual language: a solid outline means a feature exists, a dashed outline
means it is planned. The same rule is used for badges, cards and tables.
"""

from __future__ import annotations

import streamlit as st

_CSS = """
:root{
  --pn-bg:#0b1220; --pn-panel:#111a2e; --pn-raise:#16213a;
  --pn-line:#223052; --pn-line2:#34476f;
  --pn-text:#e6edf7; --pn-muted:#93a4bf; --pn-faint:#64748f;
  --pn-cyan:#22d3ee; --pn-blue:#3b82f6;
  --pn-ok:#34d399; --pn-warn:#fbbf24; --pn-plan:#8b9dc3;
  --pn-mono:"Cascadia Mono",Consolas,Menlo,monospace;
}
.stAppDeployButton,#MainMenu,footer{display:none !important;}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stMainBlockContainer"]{max-width:1480px;padding-top:2.2rem;padding-bottom:4rem;}

/* sidebar navigation */
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding-top:1.1rem;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{
  border:1px solid transparent;border-radius:9px;padding:.42rem .7rem;margin:1px 0;
  color:var(--pn-muted);transition:background-color .12s,color .12s,border-color .12s;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{
  background:rgba(34,211,238,.07);color:var(--pn-text);}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"]{
  background:rgba(34,211,238,.12);border-color:rgba(34,211,238,.45);
  color:#fff;font-weight:600;box-shadow:inset 3px 0 0 var(--pn-cyan);}
.pn-brand{display:flex;gap:.7rem;align-items:center;margin:0 0 1.1rem .2rem;}
.pn-brand-mark{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;
  color:var(--pn-cyan);border:1px solid var(--pn-line2);background:var(--pn-panel);}
.pn-brand-name{font-weight:650;font-size:1.05rem;color:var(--pn-text);line-height:1.1;}
.pn-brand-sub{font-size:.78rem;color:var(--pn-faint);margin-top:.15rem;}
.pn-nav-group{font-size:.78rem;color:var(--pn-faint);margin:1rem 0 .25rem .4rem;font-weight:600;}
.pn-sidebar-note{font-size:.8rem;color:var(--pn-muted);border-top:1px solid var(--pn-line);
  padding-top:.8rem;margin-top:1rem;line-height:1.45;}
.pn-sidebar-note b{color:var(--pn-text);font-weight:600;}

/* page header */
.pn-header{margin:0 0 1.5rem 0;padding-bottom:1.1rem;border-bottom:1px solid var(--pn-line);}
.pn-crumb{font-size:.82rem;color:var(--pn-faint);margin-bottom:.3rem;}
.pn-crumb i{font-style:normal;margin:0 .4rem;opacity:.6;}
.pn-title-row{display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;}
.pn-header h1.pn-title{margin:0 !important;padding:0 !important;font-size:1.85rem !important;
  font-weight:650 !important;letter-spacing:-.015em;color:var(--pn-text);}
.pn-sub{margin:.45rem 0 0 0;color:var(--pn-muted);max-width:62rem;font-size:.97rem;line-height:1.5;}

/* status badges: solid outline = exists, dashed = planned */
.pn-badge{display:inline-block;font-size:.76rem;font-weight:600;padding:.12rem .6rem;
  border-radius:999px;border:1px solid;line-height:1.4;white-space:nowrap;}
.pn-badge.pn-implemented{color:var(--pn-ok);border-color:rgba(52,211,153,.55);background:rgba(52,211,153,.08);}
.pn-badge.pn-experimental{color:var(--pn-warn);border-color:rgba(251,191,36,.55);background:rgba(251,191,36,.08);}
.pn-badge.pn-planned{color:var(--pn-plan);border:1px dashed rgba(139,157,195,.7);background:transparent;}

/* panels and cards */
[class*="st-key-pn-panel"]{background:var(--pn-panel);border:1px solid var(--pn-line);
  border-radius:14px;padding:1rem 1.1rem;}
.pn-card{background:var(--pn-panel);border:1px solid var(--pn-line);border-radius:14px;
  padding:1rem 1.1rem;height:100%;}
.pn-card.pn-planned{border-style:dashed;border-color:var(--pn-line2);background:transparent;}
.pn-card.pn-link:hover{border-color:var(--pn-cyan);}
.pn-card-head{display:flex;align-items:center;justify-content:space-between;gap:.6rem;margin-bottom:.5rem;}
.pn-card-title{font-weight:600;color:var(--pn-text);font-size:1rem;}
.pn-card p{margin:.2rem 0 0 0;color:var(--pn-muted);font-size:.9rem;line-height:1.5;}
.pn-ico{color:var(--pn-cyan);display:inline-flex;}
.pn-card.pn-planned .pn-ico{color:var(--pn-plan);}

/* metrics */
.pn-metric-label{display:flex;align-items:center;justify-content:space-between;
  color:var(--pn-muted);font-size:.9rem;}
.pn-metric-value{font-family:var(--pn-mono);font-size:2.3rem;font-weight:600;
  color:var(--pn-text);line-height:1.15;margin:.35rem 0 .15rem 0;font-variant-numeric:tabular-nums;}
.pn-metric-note{color:var(--pn-faint);font-size:.82rem;line-height:1.4;}

/* hero */
.pn-hero{border:1px solid var(--pn-line2);border-radius:16px;padding:1.5rem 1.7rem;
  background:var(--pn-panel);border-left:4px solid var(--pn-cyan);}
.pn-hero-title{font-size:1.9rem;font-weight:650;letter-spacing:-.015em;color:var(--pn-text);margin:0 0 .45rem 0;}
.pn-hero p{margin:0;color:var(--pn-muted);max-width:46rem;line-height:1.55;}

/* empty states and callouts */
.pn-empty{border:1px dashed var(--pn-line2);border-radius:14px;padding:1.6rem 1.2rem;
  text-align:center;color:var(--pn-muted);}
.pn-empty .pn-ico{color:var(--pn-plan);margin-bottom:.4rem;}
.pn-empty-title{color:var(--pn-text);font-weight:600;margin-bottom:.25rem;}
.pn-empty p{margin:0 auto;max-width:34rem;font-size:.92rem;line-height:1.5;}
.pn-callout{display:flex;gap:.7rem;align-items:flex-start;border:1px solid var(--pn-line);
  border-left-width:3px;border-radius:10px;padding:.7rem .9rem;margin:.2rem 0 1rem 0;
  background:var(--pn-panel);color:var(--pn-muted);font-size:.92rem;line-height:1.5;}
.pn-callout.pn-implemented{border-left-color:var(--pn-ok);}
.pn-callout.pn-experimental{border-left-color:var(--pn-warn);}
.pn-callout.pn-planned{border-left-color:var(--pn-plan);border-left-style:dashed;}
.pn-callout b{color:var(--pn-text);font-weight:600;}

/* section headings inside panels */
.pn-section{display:flex;align-items:center;justify-content:space-between;gap:.6rem;margin:0 0 .6rem 0;}
.pn-section-title{font-weight:600;color:var(--pn-text);font-size:1rem;}
.pn-section-cap{color:var(--pn-faint);font-size:.84rem;margin:-.35rem 0 .7rem 0;line-height:1.45;}

/* key/value lists and activity */
.pn-kv{display:flex;justify-content:space-between;gap:1rem;padding:.38rem 0;
  border-bottom:1px solid var(--pn-line);font-size:.9rem;}
.pn-kv:last-child{border-bottom:0;}
.pn-kv span{color:var(--pn-muted);}
.pn-kv strong{color:var(--pn-text);font-weight:500;text-align:right;word-break:break-all;
  font-family:var(--pn-mono);font-size:.85rem;}
.pn-log{display:flex;gap:.8rem;padding:.42rem 0;border-bottom:1px solid var(--pn-line);font-size:.9rem;}
.pn-log:last-child{border-bottom:0;}
.pn-log time{font-family:var(--pn-mono);color:var(--pn-faint);font-size:.82rem;min-width:4.6rem;}
.pn-log span{color:var(--pn-text);}
.pn-tag{font-family:var(--pn-mono);color:var(--pn-cyan);}

/* streamlit widgets */
button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0ea5c6,#2563eb);
  border:0;color:#fff;font-weight:600;}
button[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.1);}
button[data-testid="stBaseButton-secondary"]:hover{border-color:var(--pn-cyan);color:var(--pn-cyan);}
[data-testid="stExpander"]{border:1px solid var(--pn-line);border-radius:12px;background:var(--pn-panel);}
[data-testid="stImage"] img{border:1px solid var(--pn-line);border-radius:10px;}
"""


def apply_theme() -> None:
    """Inject the stylesheet once per rerun."""
    flat = "\n".join(line.strip() for line in _CSS.splitlines() if line.strip())
    st.html(f"<style>{flat}</style>")
