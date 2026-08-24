from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKGROUND_PATH = PROJECT_ROOT / "assets" / "library-background.png"


def _background_data_uri() -> str:
    encoded = base64.b64encode(BACKGROUND_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def apply_library_theme() -> None:
    background = _background_data_uri()
    st.html(
        f"""
        <style>
        :root {{
            --library-ink: #172033;
            --library-muted: #667085;
            --library-cream: #f7f7f3;
            --library-indigo: #5b4bdb;
            --library-violet: #7c3aed;
            --library-teal: #0f9f96;
            --library-border: #e8e9ee;
            --library-sidebar: rgba(255, 255, 255, 0.94);
            --library-sidebar-ink: #30364a;
            --library-sidebar-muted: #7d8496;
        }}

        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"],
        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stAppViewContainer"] > section.main {{ background: transparent !important; }}

        [data-testid="stAppViewContainer"] {{ position: relative; z-index: 1; }}
        .stApp {{ position: relative; isolation: isolate; min-height: 100vh; background: transparent !important; }}
        .stApp::before {{
            content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
            background-image: linear-gradient(110deg, rgba(249,249,246,.94), rgba(249,249,247,.82) 48%, rgba(244,246,246,.94)), url("{background}");
            background-size: cover; background-position: center; background-repeat: no-repeat; background-color: var(--library-cream);
        }}
        [data-testid="stHeader"], [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {{ background: transparent !important; }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(246,247,250,.96)), var(--library-sidebar) !important;
            backdrop-filter: blur(18px); border-right: 1px solid var(--library-border); box-shadow: 10px 0 34px rgba(35,31,76,.06);
        }}
        [data-testid="stSidebar"] * {{ color: var(--library-sidebar-ink); }}
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: var(--library-ink); letter-spacing: -.02em; }}
        [data-testid="stSidebarNav"] {{ padding-top: .45rem; }}
        [data-testid="stSidebarNav"] span {{ font-weight: 650; }}
        [data-testid="stSidebarNav"] a {{ border-radius: 12px; margin: .2rem .35rem; padding: .62rem .72rem; transition: background 160ms ease, transform 160ms ease; }}
        [data-testid="stSidebarNav"] a:hover {{ background: rgba(91,75,219,.08); transform: translateX(2px); }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: linear-gradient(90deg, rgba(91,75,219,.13), rgba(255,255,255,.58));
            box-shadow: inset 3px 0 0 var(--library-indigo), 0 6px 18px rgba(91,75,219,.08); color: #4338a8;
        }}
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: var(--library-sidebar-muted); }}

        .block-container {{ max-width: 1440px; padding-top: 2.3rem; padding-bottom: 4rem; }}
        [data-testid="stAppViewContainer"] .main h1, [data-testid="stAppViewContainer"] .main h2,
        [data-testid="stAppViewContainer"] .main h3 {{ color: var(--library-ink); letter-spacing: -.035em; }}
        [data-testid="stAppViewContainer"] .main p, [data-testid="stAppViewContainer"] .main label {{ color: #334155; }}
        [data-testid="stCaptionContainer"] p {{ color: var(--library-muted); }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: rgba(255,255,255,.92); border: 1px solid rgba(232,233,238,.95); border-radius: 18px;
            box-shadow: 0 14px 40px rgba(35,31,76,.07);
        }}
        [data-testid="stMetric"] {{
            background: rgba(255,255,255,.95); border: 1px solid var(--library-border); border-radius: 16px;
            box-shadow: 0 10px 28px rgba(35,31,76,.06); padding: 1rem 1.1rem;
        }}
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{ color: var(--library-ink) !important; }}
        div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, textarea {{ border-radius: 12px; border-color: var(--library-border); }}
        button[kind="primary"] {{
            background: linear-gradient(135deg, var(--library-indigo), var(--library-violet)); border-color: var(--library-indigo);
            color: white; font-weight: 750; box-shadow: 0 8px 18px rgba(91,75,219,.24);
        }}
        button[kind="secondary"] {{ border-color: #d8d9e4; color: #4b5568; background: rgba(255,255,255,.78); }}
        button[data-baseweb="tab"] {{ color: var(--library-ink); }}

        .library-topbar {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:0 0 1.25rem; padding:.35rem 0 .8rem; border-bottom:1px solid rgba(232,233,238,.9); }}
        .library-brand {{ display:flex; align-items:center; gap:.65rem; }}
        .library-mark {{ display:grid; place-items:center; width:2.2rem; height:2.2rem; border-radius:10px; color:white; font-size:1.15rem; background:linear-gradient(135deg,var(--library-indigo),var(--library-teal)); box-shadow:0 8px 18px rgba(91,75,219,.2); }}
        .library-brand-name {{ color:var(--library-ink); font-weight:800; letter-spacing:-.04em; }}
        .library-brand-sub {{ color:var(--library-muted); font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; }}
        .library-nav {{ display:flex; gap:1.3rem; color:var(--library-muted); font-size:.82rem; }}
        .library-nav span:first-child {{ color:var(--library-indigo); font-weight:700; }}

        .hero-shell {{ position:relative; overflow:hidden; padding:3.1rem 3.2rem; border:1px solid rgba(225,226,236,.95); border-radius:26px; background:linear-gradient(118deg,rgba(255,255,255,.96),rgba(250,249,255,.9)); box-shadow:0 24px 70px rgba(35,31,76,.1); }}
        .hero-shell::after {{ content:""; position:absolute; width:360px; height:360px; right:-120px; top:-160px; border-radius:50%; background:rgba(15,159,150,.12); filter:blur(4px); }}
        .hero-eyebrow, .section-kicker {{ color:var(--library-indigo); font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }}
        .hero-title {{ max-width:720px; margin:.8rem 0 .85rem; color:var(--library-ink); font-size:clamp(2.35rem,5vw,4.45rem); line-height:1.04; letter-spacing:-.065em; font-weight:850; }}
        .hero-title em {{ font-style:normal; background:linear-gradient(100deg,var(--library-indigo),var(--library-violet) 54%,var(--library-teal)); -webkit-background-clip:text; background-clip:text; color:transparent; }}
        .hero-copy {{ max-width:640px; color:#667085; font-size:1.04rem; line-height:1.72; }}
        .hero-tags {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1.25rem; }}
        .hero-tag, .tech-pill {{ display:inline-flex; align-items:center; gap:.35rem; border:1px solid #e4e5ed; border-radius:999px; padding:.42rem .72rem; color:#687187; background:rgba(255,255,255,.75); font-size:.74rem; }}
        .hero-visual {{ position:relative; z-index:1; min-height:290px; border-radius:20px; overflow:hidden; background-image:linear-gradient(135deg,rgba(25,25,80,.18),rgba(15,159,150,.08)),url("{background}"); background-size:cover; background-position:center; border:1px solid rgba(255,255,255,.7); box-shadow:0 18px 38px rgba(35,31,76,.16); }}
        .hero-visual-panel {{ position:absolute; left:1rem; right:1rem; bottom:1rem; padding:.9rem; border:1px solid rgba(255,255,255,.74); border-radius:15px; background:rgba(255,255,255,.86); backdrop-filter:blur(16px); }}
        .visual-label {{ display:flex; justify-content:space-between; color:#6b7280; font-size:.7rem; }}
        .visual-value {{ margin-top:.25rem; color:var(--library-ink); font-size:1.25rem; font-weight:800; }}
        .visual-bars {{ display:flex; align-items:end; gap:.3rem; height:44px; margin-top:.6rem; }}
        .visual-bars i {{ flex:1; border-radius:4px 4px 2px 2px; background:linear-gradient(180deg,var(--library-teal),#9bd7ce); }}

        .section-heading {{ margin:2.7rem 0 1.1rem; }}
        .section-title {{ margin:.35rem 0 0; color:var(--library-ink); font-size:1.65rem; letter-spacing:-.045em; font-weight:800; }}
        .feature-card {{ height:100%; padding:1.35rem; border:1px solid var(--library-border); border-radius:18px; background:rgba(255,255,255,.9); box-shadow:0 12px 30px rgba(35,31,76,.05); }}
        .feature-icon {{ display:grid; place-items:center; width:2.3rem; height:2.3rem; border-radius:10px; color:white; background:linear-gradient(135deg,var(--library-indigo),var(--library-violet)); }}
        .feature-card h3 {{ margin:1rem 0 .45rem; color:var(--library-ink); font-size:1.02rem; }}
        .feature-card p {{ margin:0; color:var(--library-muted); font-size:.88rem; line-height:1.65; }}
        .architecture {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.9rem; align-items:stretch; }}
        .arch-step {{ position:relative; min-height:150px; padding:1.1rem; border:1px solid var(--library-border); border-radius:16px; background:rgba(255,255,255,.86); }}
        .arch-index {{ color:var(--library-teal); font-size:.7rem; font-weight:800; letter-spacing:.12em; }}
        .arch-step h4 {{ margin:.8rem 0 .35rem; color:var(--library-ink); font-size:.98rem; }}
        .arch-step p {{ margin:0; color:var(--library-muted); font-size:.78rem; line-height:1.55; }}
        .arch-arrow {{ align-self:center; color:#a6acbb; font-size:1.2rem; text-align:center; }}
        .demo-shell {{ padding:1.25rem; border:1px solid var(--library-border); border-radius:20px; background:rgba(255,255,255,.9); box-shadow:0 14px 38px rgba(35,31,76,.06); }}
        .demo-head {{ display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:.9rem; }}
        .demo-title {{ color:var(--library-ink); font-weight:800; }}
        .online-dot {{ display:inline-flex; align-items:center; gap:.4rem; color:var(--library-teal); font-size:.72rem; }}
        .online-dot::before {{ content:""; width:.46rem; height:.46rem; border-radius:50%; background:var(--library-teal); box-shadow:0 0 0 4px rgba(15,159,150,.12); }}
        .answer-card {{ margin-top:.8rem; padding:1rem; border-radius:14px; background:linear-gradient(135deg,#f6f4ff,#f1fbf9); border:1px solid #e6e4f7; }}
        .answer-meta {{ color:var(--library-indigo); font-size:.72rem; font-weight:750; }}
        .answer-text {{ margin-top:.4rem; color:#3d4658; font-size:.86rem; line-height:1.65; }}
        .footer-cta {{ margin-top:2.8rem; padding:1.75rem 2rem; border-radius:20px; background:linear-gradient(120deg,#211c56,#4a3fc4 58%,#147e78); box-shadow:0 18px 42px rgba(35,31,76,.2); }}
        .footer-cta h2 {{ margin:0; color:white !important; font-size:1.45rem; }}
        .footer-cta p {{ margin:.45rem 0 0; color:rgba(255,255,255,.72) !important; font-size:.86rem; }}
        .page-header {{ padding:1.75rem 1.9rem; margin-bottom:1.35rem; border:1px solid rgba(225,226,236,.95); border-radius:22px; background:linear-gradient(118deg,rgba(255,255,255,.96),rgba(249,249,255,.9)); box-shadow:0 16px 44px rgba(35,31,76,.07); }}
        .page-eyebrow {{ color:var(--library-indigo); font-size:.7rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }}
        .page-title {{ margin:.45rem 0 .3rem; color:var(--library-ink); font-size:clamp(1.9rem,3.4vw,3rem); line-height:1.08; letter-spacing:-.06em; font-weight:850; }}
        .page-title em {{ font-style:normal; background:linear-gradient(100deg,var(--library-indigo),var(--library-violet) 62%,var(--library-teal)); -webkit-background-clip:text; background-clip:text; color:transparent; }}
        .page-subtitle {{ max-width:760px; margin:0; color:var(--library-muted); font-size:.92rem; line-height:1.65; }}
        .section-row {{ display:flex; align-items:end; justify-content:space-between; gap:1rem; margin:1.7rem 0 .75rem; }}
        .section-row h2 {{ margin:0; color:var(--library-ink); font-size:1.15rem; letter-spacing:-.035em; }}
        .section-row p {{ margin:.25rem 0 0; color:var(--library-muted); font-size:.8rem; }}
        .result-summary {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; margin:.4rem 0 .9rem; padding:.8rem 1rem; border:1px solid var(--library-border); border-radius:13px; background:rgba(255,255,255,.68); }}
        .result-summary strong {{ color:var(--library-ink); font-size:.9rem; }}
        .result-summary span {{ color:var(--library-muted); font-size:.76rem; }}
        .book-result-title {{ margin-bottom:.25rem; color:var(--library-ink); font-size:1.05rem; font-weight:800; letter-spacing:-.025em; }}
        .book-result-meta {{ color:var(--library-muted); font-size:.78rem; }}
        .book-result-description {{ margin-top:.6rem; color:#596579; font-size:.82rem; line-height:1.65; }}
        .book-pill {{ display:inline-flex; align-items:center; border-radius:999px; padding:.28rem .56rem; color:#4e42bb; background:#f0efff; font-size:.7rem; font-weight:700; }}
        .book-card-title {{ min-height:2.7rem; margin-top:.75rem; color:var(--library-ink); font-size:.9rem; font-weight:800; line-height:1.45; }}
        .book-card-meta {{ color:var(--library-muted); font-size:.75rem; line-height:1.55; }}
        .filter-caption {{ padding:.7rem .85rem; border-radius:12px; color:#596579; background:rgba(91,75,219,.06); font-size:.76rem; line-height:1.55; }}
        [data-testid="stChatMessage"] {{ border:1px solid rgba(232,233,238,.9); border-radius:16px; background:rgba(255,255,255,.78); box-shadow:0 8px 22px rgba(35,31,76,.04); }}
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {{ line-height:1.7; }}
        .assistant-hero {{ padding:1.45rem 1.7rem; border:1px solid rgba(225,226,236,.95); border-radius:22px; background:linear-gradient(120deg,#faf9ff,#f2fbfa); box-shadow:0 16px 44px rgba(35,31,76,.07); }}
        .assistant-hero-inner {{ display:flex; align-items:center; gap:1rem; }}
        .assistant-avatar {{ width:3rem; height:3rem; border-radius:14px; object-fit:cover; border:3px solid rgba(255,255,255,.85); box-shadow:0 8px 18px rgba(91,75,219,.18); }}
        .assistant-label {{ color:var(--library-indigo); font-size:.7rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }}
        .assistant-title {{ margin:.28rem 0; color:var(--library-ink); font-size:1.6rem; font-weight:850; letter-spacing:-.05em; }}
        .assistant-copy {{ margin:0; color:var(--library-muted); font-size:.84rem; line-height:1.6; }}
        .status-line {{ display:flex; align-items:center; gap:.5rem; margin-top:.85rem; color:var(--library-teal); font-size:.75rem; font-weight:700; }}
        .status-line::before {{ content:""; width:.45rem; height:.45rem; border-radius:50%; background:var(--library-teal); box-shadow:0 0 0 4px rgba(15,159,150,.12); }}
        .empty-state {{ padding:2rem; border:1px dashed #d9dbe8; border-radius:16px; color:var(--library-muted); background:rgba(255,255,255,.56); text-align:center; }}
        @media (max-width:900px) {{ .hero-shell {{ padding:2rem 1.3rem; }} .architecture {{ grid-template-columns:1fr 1fr; }} .arch-arrow {{ display:none; }} .library-nav {{ display:none; }} }}
        @media (max-width:600px) {{ .architecture {{ grid-template-columns:1fr; }} .hero-title {{ font-size:2.5rem; }} }}
        </style>
        """,
    )


