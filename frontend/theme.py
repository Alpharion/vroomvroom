"""RydeResolve look and feel: colour tokens, light/dark switching and small HTML pieces.

Streamlit's own theme cannot change at runtime, so the palette lives in CSS variables
that we inject on every run. The mode is "auto" (follow the OS), "light" or "dark".
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"
MODES = ["Auto", "Light", "Dark"]

_LIGHT = """
  --bg:#fff8fa; --surface:#ffffff; --surface-2:#fdeef3; --fg:#2a1822; --muted:#7a6670;
  --line:#f0d9e2; --line-strong:#d9a3b8; --line-input:#bf7a98; --accent:#e0356f; --accent-ink:#ffffff; --accent-soft:#fde1ec; --plum:#5b2a86;
  --rider:#0e8a82; --rider-soft:#dff4f1; --driver:#c26a12; --driver-soft:#fdeed8; --judge-soft:#eee4f8;
  --good:#1f8a4c; --warn:#b7791f; --warn-soft:#fbf0d9; --shadow:0 6px 24px rgba(120,40,80,.10);
  --avatar-ink:#ffffff; --verdict-a:#d8326a; --verdict-b:#5b2a86; --review-a:#a8680f;
"""
# Dark: neutral charcoal and muted, desaturated accents, so nothing glares.
_DARK = """
  --bg:#141315; --surface:#1c1b1e; --surface-2:#242227; --fg:#e8e4e7; --muted:#a29ba1;
  --line:#34313a; --line-strong:#4c4852; --line-input:#5e5964; --accent:#d9809e; --accent-ink:#1b1218; --accent-soft:#33232b; --plum:#a99bc4;
  --rider:#79aea7; --rider-soft:#1e2928; --driver:#c79e72; --driver-soft:#2b241c; --judge-soft:#25222d;
  --good:#8dbb9b; --warn:#cdb17a; --warn-soft:#2b261b; --shadow:0 6px 24px rgba(0,0,0,.45);
  --avatar-ink:#141315; --verdict-a:#5e3445; --verdict-b:#33294a; --review-a:#5a4626;
"""

_FONTS = (
    "@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800"
    "&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&display=swap');"
)

_CSS = """
:root{--z-popup:1000010;--font-display:'Plus Jakarta Sans','Segoe UI',system-ui,sans-serif;
      --font-body:'DM Sans',system-ui,-apple-system,'Segoe UI',sans-serif;}

/* ---- Streamlit surfaces ---- */
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg)!important;color:var(--fg);
  font-family:var(--font-body);}
[data-testid="stHeader"]{background:transparent!important;}
[data-testid="stSidebar"],[data-testid="stSidebar"]>div{background:var(--surface)!important;}
.stApp .block-container{max-width:1040px;padding-top:1.2rem;padding-bottom:4rem;}
.stApp :is(p,li,label,small,button,input,textarea,summary,[data-testid="stMarkdownContainer"],.vp-msg,.vp-sys,.vp-pop){font-family:var(--font-body);}
.stApp :is([data-testid="stIconMaterial"],[data-testid="stIconMaterial"] *){font-family:'Material Symbols Rounded'!important;}
.stApp :is(h1,h2,h3,h4,h5,h6){font-family:var(--font-display)!important;color:var(--fg)!important;letter-spacing:0;word-spacing:.08em;font-weight:700!important;}
.stApp :is(p,li,label,.stMarkdown,[data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"] p){color:var(--fg);}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] *{color:var(--muted)!important;}
.stApp a{color:var(--accent);}
.stApp code{background:var(--accent-soft);color:var(--accent);border-radius:6px;padding:1px 6px;}
.stApp hr{border-color:var(--line);}

/* ---- Inputs ---- */
.stApp [data-testid="stSelectbox"] [role="group"],.stApp [data-testid="stTextAreaRootElement"],
.stApp [data-testid="stTextInputRootElement"],.stApp [data-testid="stNumberInputContainer"]{
  background:var(--surface)!important;border:2px solid var(--line-input)!important;border-radius:14px!important;box-shadow:none!important;}
.stApp [data-testid="stSelectbox"] input,.stApp [data-testid="stTextAreaRootElement"] textarea,
.stApp [data-testid="stTextInputRootElement"] input,.stApp [data-testid="stNumberInputContainer"] input{
  color:var(--fg)!important;-webkit-text-fill-color:var(--fg)!important;background:transparent!important;font-family:var(--font-body);}
.stApp [data-testid="stSelectbox"] svg{fill:var(--muted)!important;}
.stApp [data-testid="stSelectbox"] [role="group"]:focus-within,.stApp [data-testid="stTextAreaRootElement"]:focus-within,
.stApp [data-testid="stTextInputRootElement"]:focus-within{border-color:var(--accent)!important;}
[data-testid="stSelectboxVirtualDropdown"],[data-testid="stSelectboxVirtualDropdown"] *,[role="listbox"],[role="listbox"] *,
[data-testid="stPopover"],[data-testid="stPopover"] *{background:var(--surface)!important;color:var(--fg)!important;}
[role="listbox"] [role="option"]:hover,[role="listbox"] [role="option"][data-focused="true"],[role="listbox"] [role="option"][aria-selected="true"]{
  background:var(--accent-soft)!important;}

/* ---- Buttons ---- */
.stApp .stButton>button,.stApp [data-testid^="stBaseButton"]{font-family:var(--font-body);font-weight:700;border-radius:14px;
  border:2px solid var(--line);background:var(--surface);color:var(--fg);transition:transform .15s,box-shadow .15s,border-color .15s;}
.stApp .stButton>button:hover{transform:translateY(-2px);border-color:var(--accent);color:var(--accent);}
.stApp [data-testid="stBaseButton-primary"],.stApp .stButton>button[kind="primary"]{
  background:var(--accent)!important;color:var(--accent-ink)!important;border-color:var(--accent)!important;
  box-shadow:0 8px 20px color-mix(in srgb,var(--accent) 35%,transparent);}
.stApp [data-testid="stBaseButton-primary"] *{color:var(--accent-ink)!important;}
.stApp .stButton>button:disabled{opacity:.5;transform:none;}

/* ---- Radio as cards, segmented control as pills ---- */
.stApp .st-key-form_dispute_type,.stApp .st-key-form_dispute_type [data-testid="stRadio"]{width:100%!important;}
.stApp .st-key-form_dispute_type [data-testid="stRadioGroup"]{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.stApp .st-key-form_dispute_type [data-testid="stRadioGroup"]>div{border:2px solid var(--line-input);border-radius:16px;padding:14px 16px;
  background:var(--surface);cursor:pointer;transition:transform .15s,border-color .15s,background .15s;}
.stApp .st-key-form_dispute_type [data-testid="stRadioGroup"]>div:hover{transform:translateY(-2px);}
.stApp .st-key-form_dispute_type [data-testid="stRadioGroup"]>div[data-selected="true"]{border-color:var(--accent);background:var(--accent-soft);}
.stApp .st-key-form_dispute_type [data-testid="stRadioOption"] p{font-weight:700;}
.stApp [data-testid="stButtonGroup"] button{border-radius:999px;border:0;background:transparent;color:var(--muted);font-weight:700;}
.stApp [data-testid="stButtonGroup"]{background:var(--surface-2);border-radius:999px;padding:4px;gap:4px;width:fit-content;}
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"],
.stApp [data-testid="stButtonGroup"] [data-testid="stBaseButton-segmented_controlActive"]{background:var(--surface)!important;color:var(--fg)!important;box-shadow:0 2px 8px rgba(0,0,0,.12);}
.stApp [data-testid="stButtonGroup"] [data-testid="stBaseButton-segmented_control"]{background:transparent;color:var(--muted);}

/* ---- Containers, expanders, tabs, alerts, status ---- */
.stApp [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]):not(:has([data-testid="stVerticalBlockBorderWrapper"])){
  border-radius:22px;}
.stApp [data-testid="stVerticalBlock"]{border-color:var(--line-strong)!important;scrollbar-color:var(--line-strong) transparent;}
.stApp [class*="st-key-evcard"]{position:relative;background:var(--surface);border:1px solid var(--line-strong);border-radius:18px;
  padding:0;box-shadow:var(--shadow);transition:transform .15s,border-color .15s,box-shadow .15s;cursor:pointer;}
.stApp [class*="st-key-evcard"]:hover{transform:translateY(-3px);border-color:var(--accent);}
.stApp [class*="st-key-evcard"]:has(button:focus-visible){outline:3px solid var(--accent);outline-offset:2px;}
.stApp [class*="st-key-evbtn"]{position:absolute!important;inset:0;width:100%!important;height:100%!important;margin:0!important;z-index:3;}
.stApp [class*="st-key-evbtn"] :is([data-testid="stButton"],div){width:100%;height:100%;}
.stApp [class*="st-key-evbtn"] button{width:100%;height:100%;opacity:0;cursor:pointer;border-radius:18px;}
.vp-evcard{display:flex;flex-direction:column;height:352px;padding:16px 18px 16px;}
.vp-evhead{font-family:var(--font-display);font-weight:600;font-size:1.25rem;color:var(--fg);margin-bottom:8px;}
.vp-evflags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;}
.vp-evbody{flex:1;min-height:0;overflow-y:auto;position:relative;z-index:4;padding-right:6px;scrollbar-width:thin;
  scrollbar-color:var(--line-strong) transparent;overscroll-behavior:contain;
  background:linear-gradient(var(--surface) 30%,transparent) top/100% 24px no-repeat local,
    linear-gradient(transparent,var(--surface) 70%) bottom/100% 24px no-repeat local,
    radial-gradient(farthest-side at 50% 0,color-mix(in srgb,var(--fg) 22%,transparent),transparent) top/100% 10px no-repeat scroll,
    radial-gradient(farthest-side at 50% 100%,color-mix(in srgb,var(--fg) 22%,transparent),transparent) bottom/100% 10px no-repeat scroll;}
.vp-evhint{color:var(--accent);font-size:.84rem;font-weight:800;padding-top:8px;}
.vp-facts.roomy{line-height:1.5;display:grid;gap:2px;padding:4px 2px;}
.vp-facts.roomy .vp-fact{display:flex;justify-content:space-between;align-items:baseline;gap:20px;padding:11px 6px;
  border-bottom:1px solid var(--line);}
.vp-facts.roomy .vp-fact .sep{display:none;}
.vp-facts.roomy .vp-fact .v{text-align:right;overflow-wrap:anywhere;}
.vp-facts.roomy .vp-fact.head{margin-top:14px;padding:9px 12px;background:var(--surface-2);border-radius:10px;border-bottom:0;
  font-family:var(--font-display);}
.stApp .st-key-view_you,.stApp [class*="st-key-view_other"]{background:var(--surface);border:1px solid var(--line-strong);
  border-radius:22px;padding:20px;box-shadow:var(--shadow);}
.stApp .st-key-view_you{border:2px solid var(--accent)!important;}
.stApp [data-testid="stExpander"] details{background:var(--surface);border:1px solid var(--line-strong)!important;border-radius:16px;}
.stApp [data-testid="stExpander"] summary{color:var(--fg);font-weight:700;background:transparent!important;}
.stApp [data-testid="stExpander"] summary:hover{background:var(--surface-2)!important;}
.stApp [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--line);}
.stApp button[role="tab"]{color:var(--muted)!important;font-weight:700;border-radius:12px 12px 0 0;}
.stApp button[role="tab"][aria-selected="true"]{color:var(--accent)!important;}
.stApp [data-baseweb="tab-highlight"]{background:var(--accent)!important;}
.stApp :is([data-testid="stAlert"],[data-testid="stAlertContainer"]){border-radius:16px;border:0;background:var(--accent-soft)!important;}
.stApp [data-testid="stAlert"] *{color:var(--fg)!important;}
.stApp [data-testid="stStatus"] details{background:var(--surface);border:1px solid var(--line)!important;border-radius:16px;}
.stApp [data-testid="stMetric"]{background:var(--surface-2);border-radius:14px;padding:10px 14px;}
.stApp [data-testid="stToggle"] label p{color:var(--fg);}

/* ---- Icons and chrome that Streamlit colours itself (config.toml is a light base) ---- */
.stApp :is([data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapseButton"],[data-testid="stSidebarCollapsedControl"],
  [data-testid="stToolbar"],[data-testid="stHeader"]) :is(button,span,svg,a){color:var(--fg)!important;}
.stApp :is([data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapseButton"],[data-testid="stSidebarCollapsedControl"],
  [data-testid="stToolbar"]) svg{fill:currentColor!important;}
.stApp [data-testid="stSelectbox"] svg,.stApp [data-testid="stNumberInputContainer"] svg,.stApp [data-testid="stExpander"] summary svg{
  fill:var(--fg)!important;color:var(--fg)!important;}
.stApp [data-testid="stIconMaterial"]{color:var(--fg);}
.stApp [data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"]{color:var(--accent-ink);}
[data-testid="stDialog"]{background:rgba(20,8,14,.62)!important;}
[data-testid="stDialog"]>div{background:var(--surface)!important;color:var(--fg)!important;border:1px solid var(--line-strong);
  border-radius:22px;box-shadow:var(--shadow);}
[data-testid="stDialog"] :is(h1,h2,h3,h4,p,span,label,li,strong,div[data-testid="stMarkdownContainer"]){color:var(--fg)!important;}
[data-testid="stDialog"] [data-testid="stCaptionContainer"] *{color:var(--muted)!important;}
[data-testid="stDialog"] button[aria-label="Close"],[data-testid="stDialog"] button[aria-label="Close"] svg{color:var(--fg)!important;fill:currentColor!important;}

/* ---- Header ---- */
.stApp .st-key-vp_header{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 90%,transparent);
  backdrop-filter:blur(8px);padding:8px 0 10px;border-bottom:1px solid var(--line);margin-bottom:8px;}
.stApp .st-key-vp_header [data-testid="stPageLink"] a{border-radius:999px;padding:6px 12px;font-weight:700;text-decoration:none;}
.stApp .st-key-vp_header [data-testid="stPageLink"] a p{color:var(--muted);font-size:.92rem;}
.stApp .st-key-vp_header [data-testid="stPageLink"] a[aria-current="page"]{background:var(--accent-soft);}
.stApp .st-key-vp_header [data-testid="stPageLink"] a[aria-current="page"] p{color:var(--accent);}
.vp-brand{display:flex;align-items:center;gap:10px;font-family:var(--font-display);font-weight:700;font-size:1.35rem;color:var(--fg);}
.vp-mark{width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,var(--accent),var(--plum));display:grid;place-items:center;}

/* ---- Hero ---- */
.vp-eyebrow{font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;font-weight:800;color:var(--accent);}
.vp-hero{display:grid;grid-template-columns:1.1fr .9fr;gap:32px;align-items:center;padding:28px 0 8px;}
.vp-hero h1{font-size:clamp(1.9rem,4.4vw,3rem);line-height:1.14;letter-spacing:-.01em;word-spacing:.08em;margin:10px 0 14px;font-weight:700;}
.vp-hero h1 em{font-style:normal;background:linear-gradient(90deg,var(--accent),var(--plum));-webkit-background-clip:text;
  background-clip:text;color:transparent;}
.vp-lead{color:var(--muted)!important;font-size:1.1rem;max-width:46ch;}
.vp-art{position:relative;aspect-ratio:5/4;max-width:100%;border-radius:28px;overflow:hidden;box-shadow:var(--shadow);
  background:linear-gradient(150deg,var(--accent-soft),var(--judge-soft));}
.vp-art svg,.vp-art img{width:100%;height:100%;display:block;object-fit:cover;}
.vp-how{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:18px 0 8px;}
.vp-how>div{background:var(--surface);border:1px solid var(--line-strong);border-radius:18px;padding:18px;}
.vp-how h3{font-size:1.05rem;margin:0 0 4px;}
.vp-how p{color:var(--muted)!important;font-size:.94rem;margin:0;}
.vp-sec{display:grid;gap:4px;margin:26px 0 14px;}
.vp-sec h2{font-size:clamp(1.4rem,3.2vw,1.9rem);margin:0;}
.vp-sec p{color:var(--muted)!important;max-width:60ch;margin:0;}
.vp-car{animation:vp-drive 5s ease-in-out infinite alternate;}

/* ---- Stepper ---- */
.vp-steps{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 14px;}
.vp-step{padding:5px 14px;border-radius:999px;border:1px solid var(--line-strong);color:var(--muted);font-size:.86rem;font-weight:700;}
.vp-step.done{background:var(--accent-soft);color:var(--accent);border-color:transparent;}
.vp-step.now{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);animation:vp-pulse 1.8s ease-in-out infinite;}

/* ---- Chat ---- */
.vp-chat{display:grid;gap:14px;padding:4px;}
.vp-msg{display:grid;grid-template-columns:40px minmax(0,1fr);gap:10px;max-width:min(580px,94%);}
.vp-msg:last-child{animation:vp-rise .5s ease both;}
.vp-msg.rider,.vp-msg.driver{width:min(580px,94%);}
.vp-msg.driver{margin-left:auto;grid-template-columns:minmax(0,1fr) 40px;}
.vp-msg.driver .vp-avatar{order:2;}
.vp-msg.judge{max-width:100%;margin-inline:auto;width:min(660px,100%);}
.vp-avatar{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font-family:var(--font-display);font-weight:700;color:var(--avatar-ink);}
.rider .vp-avatar{background:var(--rider);} .driver .vp-avatar{background:var(--driver);} .judge .vp-avatar{background:var(--plum);}
.vp-bubble{font-size:.96rem;line-height:1.5;border-radius:18px;padding:12px 16px;min-width:0;overflow-wrap:anywhere;color:var(--fg);}
.rider .vp-bubble{background:var(--rider-soft);border-top-left-radius:6px;}
.driver .vp-bubble{background:var(--driver-soft);border-top-right-radius:6px;}
.judge .vp-bubble{background:var(--judge-soft);}
.vp-who{font-size:.8rem;font-weight:800;margin-bottom:2px;}
.rider .vp-who{color:var(--rider);} .driver .vp-who{color:var(--driver);} .judge .vp-who{color:var(--plum);}
.vp-msg.cont{margin-top:-8px;}
.vp-msg.cont .vp-avatar{visibility:hidden;}
.vp-claim{color:var(--fg);}
.vp-tag{font-size:.68rem;font-weight:800;color:var(--muted);background:var(--surface);border:1px solid var(--line-strong);
  border-radius:999px;padding:0 8px;margin-left:8px;letter-spacing:.03em;vertical-align:1px;}
.vp-based{margin-top:8px;font-size:.88rem;color:var(--muted);line-height:1.45;}
.vp-based b{font-style:normal;font-weight:800;font-size:.68rem;letter-spacing:.07em;text-transform:uppercase;margin-right:6px;}
.vp-based em{font-style:italic;}
.vp-based code{background:var(--surface);color:var(--fg);}
.vp-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;}
.vp-chip{position:relative;font-size:.74rem;font-weight:800;padding:2px 9px;border-radius:999px;background:var(--surface);color:var(--fg);
  border:1px solid var(--line-strong);cursor:help;transition:border-color .15s,background .15s;}
.vp-chip:hover,.vp-chip:focus{border-color:var(--accent);background:var(--accent-soft);outline:none;}
.vp-chip:focus-visible{outline:3px solid var(--accent);outline-offset:2px;}
/* The chat scrolls and clips, so its popups are fixed: a bottom sheet by default, anchored to the chip where supported. */
.vp-chip .vp-pop{position:fixed;left:12px;right:12px;bottom:12px;width:auto;padding-bottom:0;}
.vp-chip:hover .vp-pop,.vp-chip:focus .vp-pop{display:block;animation:vp-rise .18s ease both;}
@supports (position-anchor:--x){
  .vp-chip .vp-pop{position-anchor:var(--vp-anchor);right:auto;bottom:anchor(top);left:anchor(left);width:min(340px,86vw);
    padding-bottom:10px;position-try-fallbacks:flip-inline,flip-block,flip-block flip-inline;}
}
.vp-sys{text-align:center;color:var(--muted);font-size:.88rem;background:var(--surface);border:1px dashed var(--line);
  border-radius:18px;padding:6px 16px;margin-inline:auto;max-width:100%;}
.vp-typing{display:inline-flex;gap:4px;padding:6px 2px;}
.vp-typing i{width:7px;height:7px;border-radius:50%;background:var(--plum);animation:vp-bounce 1.2s infinite ease-in-out;}
.vp-typing i:nth-child(2){animation-delay:.15s;} .vp-typing i:nth-child(3){animation-delay:.3s;}

/* ---- Verdict and ruling cards ---- */
.vp-verdict{background:linear-gradient(135deg,var(--verdict-a),var(--verdict-b));color:#fff;border-radius:26px;padding:26px;display:flex;gap:20px;
  align-items:center;justify-content:space-between;flex-wrap:wrap;box-shadow:var(--shadow);animation:vp-pop .6s cubic-bezier(.2,1.3,.4,1) both;}
.vp-verdict.review{background:linear-gradient(135deg,var(--review-a),var(--verdict-b));}
.vp-verdict h3{font-size:clamp(1.3rem,3.2vw,1.9rem);margin:0 0 4px;color:#fff!important;}
.vp-verdict p{margin:0;color:#fff!important;opacity:.92;}
.vp-amount{font-family:var(--font-display);font-weight:700;font-size:3rem;font-variant-numeric:tabular-nums;color:#fff;}
.vp-meter{height:8px;border-radius:999px;background:var(--surface-2);overflow:hidden;margin:6px 0;}
.vp-meter i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--plum));border-radius:inherit;
  transform-origin:left;animation:vp-grow 1s ease both;}
.vp-pill{display:inline-block;font-size:.78rem;font-weight:800;padding:3px 10px;border-radius:999px;background:var(--accent-soft);color:var(--accent);}
.vp-pill.good{background:color-mix(in srgb,var(--good) 18%,transparent);color:var(--good);}
.vp-pill.warn{background:var(--warn-soft);color:var(--warn);}
.vp-viewhead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:4px;}
.vp-viewhead h3{margin:0;font-size:1.2rem;}
.vp-why{color:var(--fg);margin:8px 0;}
.vp-refs{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid var(--line);}
.vp-refs-label{font-size:.72rem;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-right:2px;}
.vp-pill.bad{background:var(--accent-soft);color:var(--accent);}
.vp-claims{margin-top:18px;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:var(--surface);}
.vp-claim{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:start;padding:10px 0;border-bottom:1px solid var(--line);}
.vp-claim:last-of-type{border-bottom:0;}
.vp-claim p{margin:0 0 2px;}
.vp-claim .vp-pill{white-space:nowrap;}
.vp-claim-record{color:var(--muted);}
.vp-claim-refs code{font-size:.75rem;margin-right:6px;}
.vp-claim-note{margin:8px 0 0;font-size:.82rem;color:var(--muted);}
@media (max-width:640px){.vp-claim{grid-template-columns:1fr;}}
.vp-clause{position:relative;display:inline-block;font-size:.8rem;font-weight:800;padding:3px 11px;border-radius:999px;cursor:help;
  background:var(--surface);color:var(--fg);border:1px solid var(--line-strong);transition:border-color .15s,background .15s;}
.vp-clause:hover,.vp-clause:focus{border-color:var(--accent);background:var(--accent-soft);outline:none;}
.vp-clause:focus-visible{outline:3px solid var(--accent);outline-offset:2px;}
.vp-pop{display:none;position:absolute;z-index:var(--z-popup);bottom:100%;left:0;width:min(340px,72vw);padding-bottom:10px;
  text-align:left;font-weight:400;cursor:default;}
.vp-clause.right .vp-pop{left:auto;right:0;}
.vp-pop>b,.vp-pop>span{display:block;background:var(--surface);color:var(--fg);border-left:1px solid var(--line-strong);
  border-right:1px solid var(--line-strong);padding:0 14px;}
.vp-pop>b{border-top:1px solid var(--line-strong);border-radius:14px 14px 0 0;padding-top:12px;font-family:var(--font-display);
  font-weight:600;font-size:.95rem;color:var(--accent);}
.vp-pop>span{border-bottom:1px solid var(--line-strong);border-radius:0 0 14px 14px;padding-bottom:12px;padding-top:4px;
  font-size:.86rem;line-height:1.5;box-shadow:0 14px 30px rgba(0,0,0,.28);}
.vp-clause:hover .vp-pop,.vp-clause:focus .vp-pop,.vp-clause:focus-within .vp-pop{display:block;animation:vp-rise .18s ease both;}

/* ---- Evidence tiles ---- */
.vp-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:14px;}
.vp-tile{background:var(--surface);border:1px solid var(--line-strong);border-radius:16px;padding:14px 16px;}
.vp-tile b{display:block;font-family:var(--font-display);font-size:1.7rem;font-variant-numeric:tabular-nums;color:var(--fg);}
.vp-tile span{color:var(--muted);font-size:.86rem;}
.vp-legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:.88rem;margin-top:6px;}
.vp-legend i{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px;vertical-align:-1px;}
.vp-tile.flag{background:var(--driver-soft);border-color:transparent;}

@keyframes vp-rise{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes vp-pop{from{opacity:0;transform:scale(.94);}to{opacity:1;transform:none;}}
@keyframes vp-grow{from{transform:scaleX(0);}to{transform:scaleX(1);}}
@keyframes vp-bounce{0%,60%,100%{transform:translateY(0);opacity:.5;}30%{transform:translateY(-5px);opacity:1;}}
@keyframes vp-pulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 45%,transparent);}50%{box-shadow:0 0 0 7px transparent;}}
@keyframes vp-drive{from{transform:translateX(-30px);}to{transform:translateX(30px);}}
@media (max-width:760px){
  .vp-pop{position:fixed;left:12px!important;right:12px!important;bottom:12px;width:auto;padding-bottom:0;}
  .vp-hero,.vp-how{grid-template-columns:1fr;}
  .stApp .st-key-form_dispute_type [data-testid="stRadioGroup"]{grid-template-columns:1fr;}
  .stApp .st-key-vp_header{position:static;}
  .vp-msg{max-width:100%;}
}
@media (max-width:880px){
  /* With the sidebar open the content area is narrow: show clause popups as a bottom sheet, above the sidebar. */
  .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .vp-pop{position:fixed;left:12px!important;right:12px!important;
    bottom:12px;width:auto;padding-bottom:0;}
}
@media (prefers-reduced-motion:reduce){.stApp *,.vp-verdict,.vp-car{animation:none!important;transition:none!important;}}
"""


def _tokens(mode: str) -> str:
    if mode == "Light":
        return f":root{{{_LIGHT}color-scheme:light;}}"
    if mode == "Dark":
        return f":root{{{_DARK}color-scheme:dark;}}"
    return (
        f":root{{{_LIGHT}color-scheme:light;}}"
        f"@media (prefers-color-scheme:dark){{:root{{{_DARK}color-scheme:dark;}}}}"
    )


def current_mode() -> str:
    mode = st.session_state.get("theme_mode")
    return mode if mode in MODES else "Auto"


def is_dark() -> bool:
    """True when the dark palette is explicitly chosen (Auto cannot be known server-side)."""
    return current_mode() == "Dark"


def inject_theme() -> None:
    st.markdown(f"<style>{_FONTS}{_tokens(current_mode())}{_CSS}</style>", unsafe_allow_html=True)


def _hero_art() -> str:
    for name in ("hero.png", "hero.jpg", "hero.jpeg", "hero.webp", "hero.svg"):
        path = ASSETS / name
        if path.is_file():
            mime = "image/svg+xml" if name.endswith(".svg") else f"image/{name.rsplit('.', 1)[1].replace('jpg', 'jpeg')}"
            data = base64.b64encode(path.read_bytes()).decode()
            return f'<img alt="A car on a winding road heading to a map pin" src="data:{mime};base64,{data}">'
    return (
        '<svg viewBox="0 0 500 400" preserveAspectRatio="xMidYMid slice" role="img" '
        'aria-label="A car on a winding road heading to a map pin">'
        '<circle cx="400" cy="90" r="46" fill="var(--accent)" opacity=".25"/>'
        '<circle cx="90" cy="320" r="70" fill="var(--plum)" opacity=".15"/>'
        '<path d="M-10 330 C 110 250, 170 360, 270 270 S 430 190, 520 230" fill="none" stroke="var(--surface)" '
        'stroke-width="46" stroke-linecap="round"/>'
        '<path d="M-10 330 C 110 250, 170 360, 270 270 S 430 190, 520 230" fill="none" stroke="var(--line)" '
        'stroke-width="3" stroke-dasharray="14 16" stroke-linecap="round"/>'
        '<g class="vp-car"><g transform="translate(150 262)">'
        '<rect x="0" y="-26" width="76" height="30" rx="12" fill="var(--accent)"/>'
        '<rect x="14" y="-40" width="42" height="22" rx="9" fill="var(--accent)"/>'
        '<rect x="22" y="-36" width="26" height="14" rx="5" fill="var(--surface)" opacity=".9"/>'
        '<circle cx="18" cy="6" r="9" fill="var(--fg)"/><circle cx="58" cy="6" r="9" fill="var(--fg)"/></g></g>'
        '<g transform="translate(405 150)"><path d="M0 0 C -22 -30, -22 -56, 0 -56 C 22 -56, 22 -30, 0 0z" fill="var(--plum)"/>'
        '<circle cx="0" cy="-38" r="8" fill="var(--surface)"/></g></svg>'
    )


def brand_html() -> str:
    return (
        '<div class="vp-brand"><span class="vp-mark" aria-hidden="true">'
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M3 15l2-5a2 2 0 0 1 2-1.4h10a2 2 0 0 1 2 1.4l2 5v3H3z"/>'
        '<circle cx="7.5" cy="18" r="1.6" fill="#fff"/><circle cx="16.5" cy="18" r="1.6" fill="#fff"/></svg></span>'
        "RydeResolve</div>"
    )


def hero_html() -> str:
    return (
        '<div class="vp-hero"><div><div class="vp-eyebrow">Rider and driver disputes</div>'
        "<h1>Something went wrong on the ride? <em>Get a fair answer in about a minute.</em></h1>"
        '<p class="vp-lead">Tell us what happened. One advocate speaks for the rider, one for the driver, '
        "and a judge decides. You can watch every step.</p></div>"
        f'<div class="vp-art">{_hero_art()}</div></div>'
        '<div class="vp-how">'
        "<div><h3>You tell us</h3><p>Pick the trip and describe what happened in your own words.</p></div>"
        "<div><h3>Both sides are heard</h3><p>An advocate for each side gathers the evidence and cites the policy.</p></div>"
        "<div><h3>A judge decides</h3><p>You get a clear ruling for each of you. Safety cases always go to a person.</p></div></div>"
    )


def section_head(eyebrow: str, title: str, sub: str = "") -> None:
    sub_html = f"<p>{sub}</p>" if sub else ""
    st.markdown(
        f'<div class="vp-sec"><div class="vp-eyebrow">{eyebrow}</div><h2>{title}</h2>{sub_html}</div>',
        unsafe_allow_html=True,
    )
