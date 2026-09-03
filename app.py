
import copy
import json
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg2
import requests
import streamlit as st


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="NEXUS — Personal OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "PUBLIC V1.5 • QUICK ACCESS COMMAND CENTER"
DEFAULT_TZ = "America/Los_Angeles"


PAGE_ICONS = {
    "Dashboard": "⚡",
    "School": "🎓",
    "Money": "💰",
    "Fitness": "🏋️",
    "Intel": "◈",
    "Assistant": "✦",
}


# ============================================================
# STATE
# ============================================================

def default_state():
    return {
        "profile": {
            "name": "",
            "system_name": "NEXUS",
            "timezone": DEFAULT_TZ,
            "onboarded": False,
            "modules": ["School", "Money", "Fitness", "Intel", "Assistant"],
            "primary_goal": "Stay organized",
        },
        "tasks": [],
        "manual_assignments": [],
        "canvas": {
            "base_url": "",
            "token": "",
            "connected": False,
            "assignments": [],
            "error": None,
            "last_sync": None,
        },
        "money": {
            "savings": 0.0,
            "goal": 5000.0,
            "income": [],
            "expenses": [],
        },
        "fitness": {
            "weight": None,
            "goal_weight": None,
            "history": [],
            "workouts": [],
        },
        "intel": {
            "radar": [],
            "captures": [],
        },
        "assistant_history": [],
        "openai": {
            "api_key": "",
            "model": "gpt-5-mini",
        },
    }


# ============================================================
# AUTH + CLOUD PERSISTENCE
# ============================================================

def database_url():
    try:
        return str(st.secrets["DATABASE_URL"]).strip()
    except Exception:
        return ""


def user_claim(name, default=""):
    try:
        value = st.user.get(name, default)
    except Exception:
        value = default
    return value or default


def user_id():
    # Google's OIDC "sub" claim is stable for the user within this client.
    return str(user_claim("sub", "")).strip()


def user_email():
    return str(user_claim("email", "")).strip()


def user_display_name():
    return str(user_claim("name", "")).strip()


def sanitized_state_for_cloud(state):
    """
    Persist the user's NEXUS data while intentionally excluding credentials
    that should remain session-only.
    """
    safe = copy.deepcopy(state)

    safe.setdefault("canvas", {})
    safe["canvas"]["token"] = ""
    safe["canvas"]["connected"] = False
    safe["canvas"]["error"] = None

    safe.setdefault("openai", {})
    safe["openai"]["api_key"] = ""

    return safe


def merge_with_defaults(saved):
    base = default_state()
    if not isinstance(saved, dict):
        return base

    # Top-level merge, then merge nested dictionaries used by the app.
    for key, value in saved.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key].update(value)
        else:
            base[key] = value

    # Backward compatibility for users created before cloud accounts.
    profile = base.setdefault("profile", {})
    if "onboarded" not in profile:
        profile["onboarded"] = bool(profile.get("name"))
    return base


def init_database():
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is missing from Streamlit Secrets.")

    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS nexus_user_data (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    display_name TEXT,
                    app_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
        conn.commit()


def load_cloud_state(uid):
    url = database_url()
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT app_data FROM nexus_user_data WHERE user_id = %s;",
                (uid,),
            )
            row = cur.fetchone()

    if not row:
        return default_state(), False

    payload = row[0]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return merge_with_defaults(payload), True


def persist_cloud_state(state):
    uid = user_id()
    if not uid:
        return

    safe = sanitized_state_for_cloud(state)
    payload = json.dumps(safe, default=str)

    with psycopg2.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus_user_data
                    (user_id, email, display_name, app_data, updated_at)
                VALUES
                    (%s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    app_data = EXCLUDED.app_data,
                    updated_at = NOW();
                """,
                (
                    uid,
                    user_email(),
                    user_display_name(),
                    payload,
                ),
            )
        conn.commit()


def save_state():
    st.session_state.public_data = data
    try:
        persist_cloud_state(data)
        st.session_state["cloud_save_error"] = None
    except Exception:
        # Never print the connection string or database credentials.
        st.session_state["cloud_save_error"] = (
            "NEXUS could not save to the cloud right now."
        )


# Require a Google account before loading any private user data.
if not st.user.is_logged_in:
    st.markdown(
        """
        <div style="
            max-width:760px;
            margin:10vh auto 0 auto;
            padding:2rem;
            border:1px solid rgba(103,215,255,.22);
            border-radius:22px;
            background:rgba(13,19,31,.88);
        ">
            <div style="font-size:.78rem;letter-spacing:.16em;color:#67d7ff;font-weight:800;">
                NEXUS PERSONAL OS
            </div>
            <div style="font-size:2.35rem;font-weight:900;margin:.35rem 0 .55rem 0;">
                Your system. Anywhere.
            </div>
            <div style="color:#91a0ba;font-size:1.03rem;line-height:1.65;">
                Sign in with Google to create your private NEXUS profile and sync
                your school, money, fitness, goals, Intel, and assistant history
                across devices.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    left, center, right = st.columns([1, 1.2, 1])
    with center:
        if st.button("Continue with Google", type="primary", use_container_width=True):
            st.login()
        st.caption("Your Canvas token and personal OpenAI API key are never stored in the NEXUS cloud database.")
    st.stop()


uid = user_id()
if not uid:
    st.error("Google sign-in succeeded, but NEXUS did not receive a usable user ID.")
    if st.button("Log out"):
        st.logout()
    st.stop()


# Initialize the database and load this user's data only once per login/session.
try:
    init_database()
except Exception:
    st.error(
        "NEXUS could not connect to its cloud database. "
        "Check the DATABASE_URL secret and redeploy."
    )
    st.stop()


loaded_uid = st.session_state.get("nexus_loaded_uid")
if loaded_uid != uid:
    try:
        loaded_state, existing_user = load_cloud_state(uid)
    except Exception:
        st.error("NEXUS could not load your cloud profile right now.")
        st.stop()

    st.session_state.public_data = loaded_state
    st.session_state.nexus_loaded_uid = uid
    st.session_state.nexus_existing_user = existing_user
    st.session_state.current_page = "Dashboard"
    st.session_state.pop("nexus_onboarded", None)


if "public_data" not in st.session_state:
    st.session_state.public_data = default_state()

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

data = st.session_state.public_data

# Navigation depends on this signed-in user's saved module choices.
PAGES = ["Dashboard"] + [
    module
    for module in data.get("profile", {}).get(
        "modules",
        ["School", "Money", "Fitness", "Intel", "Assistant"],
    )
    if module in ["School", "Money", "Fitness", "Intel", "Assistant"]
]

# If this Google account already has a completed cloud profile, skip onboarding.
if data.get("profile", {}).get("onboarded"):
    st.session_state.nexus_onboarded = True


def now_local():
    tz_name = data.get("profile", {}).get("timezone") or DEFAULT_TZ
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(DEFAULT_TZ)
    return datetime.now(tz)


def go_to(page_name):
    if page_name in PAGES:
        st.session_state.current_page = page_name
        st.rerun()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def system_name():
    value = (data.get("profile", {}).get("system_name") or "NEXUS").strip()
    return value or "NEXUS"


def owner_name():
    return (data.get("profile", {}).get("name") or "").strip()


def enabled_modules():
    modules = data.get("profile", {}).get("modules") or []
    return [m for m in modules if m in ["School", "Money", "Fitness", "Intel", "Assistant"]]


def module_enabled(name):
    return name in enabled_modules()


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --bg: #070a11;
        --panel: rgba(13, 19, 31, 0.88);
        --panel2: rgba(18, 26, 43, 0.78);
        --line: rgba(124, 166, 255, 0.18);
        --text: #f6f8ff;
        --muted: #91a0ba;
        --cyan: #67d7ff;
        --purple: #b995ff;
        --pink: #ff6fae;
        --green: #5ee6a8;
        --orange: #ffb86b;
        --red: #ff6b78;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 10%, rgba(54, 126, 255, .12), transparent 28%),
            radial-gradient(circle at 85% 15%, rgba(158, 91, 255, .10), transparent 30%),
            linear-gradient(180deg, #070a11 0%, #090d16 100%);
        color: var(--text);
    }

    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, rgba(9, 13, 22, .98), rgba(8, 11, 18, .98));
        border-right: 1px solid rgba(110, 151, 235, .14);
    }

    .mc-brand {
        font-size: 1.15rem;
        font-weight: 900;
        letter-spacing: .08em;
        padding: .2rem 0 .7rem;
    }

    .mc-kicker {
        color: var(--cyan);
        font-size: .74rem;
        letter-spacing: .16em;
        font-weight: 800;
        text-transform: uppercase;
    }

    .mc-title {
        font-size: clamp(2rem, 5vw, 4rem);
        font-weight: 950;
        line-height: .95;
        letter-spacing: -.045em;
        margin: .35rem 0 .6rem;
    }

    .mc-subtitle {
        color: var(--muted);
        font-size: 1rem;
        max-width: 900px;
        line-height: 1.55;
    }

    .mc-hero {
        border: 1px solid rgba(112, 161, 255, .18);
        background:
            linear-gradient(135deg, rgba(21, 42, 73, .50), rgba(21, 18, 48, .42));
        border-radius: 24px;
        padding: 1.35rem 1.4rem;
        margin: .2rem 0 1rem;
        box-shadow: 0 20px 70px rgba(0,0,0,.25);
    }

    .mc-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: .85rem;
        margin: .8rem 0 1.1rem;
    }

    .mc-card {
        border: 1px solid rgba(124, 166, 255, .16);
        border-radius: 18px;
        padding: 1rem;
        background: rgba(12, 18, 30, .82);
        min-height: 118px;
    }

    .mc-card.cyan { box-shadow: inset 3px 0 0 rgba(103, 215, 255, .8); }
    .mc-card.purple { box-shadow: inset 3px 0 0 rgba(185, 149, 255, .8); }
    .mc-card.green { box-shadow: inset 3px 0 0 rgba(94, 230, 168, .8); }
    .mc-card.pink { box-shadow: inset 3px 0 0 rgba(255, 111, 174, .8); }
    .mc-card.orange { box-shadow: inset 3px 0 0 rgba(255, 184, 107, .8); }

    .mc-label {
        color: var(--muted);
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: .13em;
        text-transform: uppercase;
        margin-bottom: .45rem;
    }

    .mc-value {
        color: var(--text);
        font-size: 1.65rem;
        font-weight: 900;
        letter-spacing: -.025em;
    }

    .mc-detail {
        color: var(--muted);
        margin-top: .35rem;
        font-size: .88rem;
    }

    .mc-section {
        margin-top: 1.3rem;
        color: #dfe8ff;
        letter-spacing: .08em;
        font-size: .8rem;
        font-weight: 900;
        text-transform: uppercase;
    }

    .mc-pill {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        border: 1px solid rgba(121, 163, 244, .20);
        background: rgba(16, 24, 39, .75);
        color: #dce8ff;
        border-radius: 999px;
        padding: .32rem .62rem;
        font-size: .76rem;
        margin: .12rem .12rem .12rem 0;
    }

    .mc-radar {
        border: 1px solid rgba(185, 149, 255, .20);
        border-radius: 18px;
        padding: .85rem 1rem;
        margin: .6rem 0;
        background: linear-gradient(90deg, rgba(86, 57, 145, .14), rgba(12, 18, 30, .65));
    }

    .mc-task {
        border: 1px solid rgba(124, 166, 255, .14);
        border-radius: 14px;
        padding: .75rem .85rem;
        background: rgba(10, 16, 27, .72);
        margin-bottom: .55rem;
    }

    .mc-task-title {
        font-weight: 800;
        color: #f6f9ff;
    }

    .mc-task-meta {
        color: var(--muted);
        font-size: .82rem;
        margin-top: .2rem;
    }

    .mc-note {
        border: 1px solid rgba(94, 230, 168, .17);
        background: rgba(29, 94, 70, .10);
        border-radius: 16px;
        padding: .85rem 1rem;
        color: #dfffee;
    }

    div[data-testid="stMetric"] {
        background: rgba(12, 18, 30, .74);
        border: 1px solid rgba(124, 166, 255, .14);
        padding: .85rem;
        border-radius: 16px;
    }

    .stButton > button {
        border-radius: 12px;
        border: 1px solid rgba(116, 163, 255, .26);
        background: rgba(15, 23, 38, .88);
        color: #f5f8ff;
    }

    .stButton > button:hover {
        border-color: rgba(103, 215, 255, .70);
        color: white;
    }

    @media (max-width: 700px) {
        .mc-title { font-size: 2.4rem; }
        .mc-grid { grid-template-columns: 1fr 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)



st.markdown(
    """
    <style>
    :root {
        --nx-bg: #050811;
        --nx-panel: rgba(12,18,31,.90);
        --nx-panel2: rgba(15,23,39,.86);
        --nx-line: rgba(126,162,230,.15);
        --nx-text: #f7f9ff;
        --nx-muted: #8390a8;
        --nx-cyan: #3ad9ff;
        --nx-blue: #4b92ff;
        --nx-purple: #a978ff;
        --nx-pink: #ff65c8;
        --nx-green: #42db82;
        --nx-red: #ff626e;
    }

    .stApp {
        background:
            radial-gradient(circle at 4% 0%, rgba(75,146,255,.18), transparent 27%),
            radial-gradient(circle at 96% 3%, rgba(169,120,255,.13), transparent 25%),
            radial-gradient(circle at 82% 88%, rgba(255,101,200,.055), transparent 24%),
            linear-gradient(180deg, #070b13 0%, #050811 58%, #04070d 100%);
    }

    header[data-testid="stHeader"] {
        background: rgba(5,8,16,.70);
        backdrop-filter: blur(18px);
        border-bottom: 1px solid rgba(255,255,255,.035);
    }

    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 12% 0%, rgba(75,146,255,.12), transparent 28%),
            radial-gradient(circle at 92% 24%, rgba(169,120,255,.08), transparent 24%),
            linear-gradient(180deg, #09101b 0%, #070b12 100%);
        border-right: 1px solid rgba(126,162,230,.13);
    }

    .block-container {
        max-width: 1240px;
        padding-top: 1rem;
        padding-bottom: 4rem;
    }

    .mc-hero {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(126,162,230,.16);
        background:
            radial-gradient(circle at 90% 12%, rgba(169,120,255,.17), transparent 30%),
            linear-gradient(135deg, rgba(15,25,43,.96), rgba(8,13,23,.94));
        border-radius: 21px;
        padding: 1.25rem 1.35rem;
        box-shadow: 0 22px 70px rgba(0,0,0,.21);
    }

    .mc-hero::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        height: 3px;
        width: 100%;
        background: linear-gradient(90deg, #3ad9ff, #4b92ff, #a978ff, #ff65c8);
    }

    .mc-kicker {
        color: #4bdcff;
        font-size: .70rem;
        font-weight: 900;
        letter-spacing: .19em;
    }

    .mc-title {
        color: #f8fbff;
        font-size: clamp(2.35rem, 6vw, 4.2rem);
        font-weight: 950;
        letter-spacing: -.055em;
        line-height: .95;
        margin-top: .38rem;
    }

    .mc-subtitle {
        color: #8a98b0;
        max-width: 790px;
    }

    .mc-section {
        color: #dfe8ff;
        letter-spacing: .13em;
        font-size: .72rem;
        font-weight: 950;
        margin-top: 1.45rem;
    }

    .mc-card,
    .mc-task,
    .mc-radar,
    .mc-note,
    div[data-testid="stMetric"] {
        border-color: rgba(126,162,230,.13);
        background: linear-gradient(180deg, rgba(15,23,39,.91), rgba(8,14,24,.88));
        box-shadow: 0 14px 38px rgba(0,0,0,.13);
    }

    .nx-module-card {
        position: relative;
        overflow: hidden;
        border-radius: 18px;
        border: 1px solid rgba(126,162,230,.15);
        background: linear-gradient(180deg, rgba(15,23,39,.94), rgba(8,14,24,.92));
        padding: 1rem 1.05rem;
        min-height: 142px;
        margin-bottom: .65rem;
    }

    .nx-module-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        height: 3px;
        width: 100%;
        background: linear-gradient(
            90deg,
            var(--c1, #3ad9ff),
            var(--c2, #a978ff)
        );
    }

    .nx-module-card.purple { --c1:#a978ff; --c2:#ff65c8; }
    .nx-module-card.green { --c1:#42db82; --c2:#42e5c5; }
    .nx-module-card.pink { --c1:#ff626e; --c2:#ff65c8; }
    .nx-module-card.cyan { --c1:#3ad9ff; --c2:#4b92ff; }
    .nx-module-card.blue { --c1:#4b92ff; --c2:#a978ff; }

    .nx-eye {
        color: #78869e;
        font-size: .67rem;
        font-weight: 950;
        letter-spacing: .16em;
    }

    .nx-big {
        color: #f9fbff;
        font-size: 2rem;
        font-weight: 950;
        letter-spacing: -.04em;
        margin-top: .34rem;
    }

    .nx-label {
        color: #dce6f8;
        font-size: .88rem;
        font-weight: 850;
        margin-top: .06rem;
    }

    .nx-detail {
        color: #79879f;
        font-size: .77rem;
        margin-top: .32rem;
    }

    .stButton > button {
        border-radius: 11px;
        border: 1px solid rgba(116,163,255,.25);
        background: rgba(14,22,37,.90);
        color: #f6f9ff;
        font-weight: 760;
    }

    .stButton > button:hover {
        border-color: rgba(58,217,255,.68);
        box-shadow: 0 0 0 1px rgba(58,217,255,.08), 0 10px 30px rgba(0,0,0,.18);
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    textarea {
        background: rgba(10,16,28,.92);
        border-color: rgba(126,162,230,.16);
    }

    @media (max-width: 700px) {
        .mc-title { font-size: 2.55rem; }
        .nx-module-card { min-height: 128px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)



st.markdown(
    """
    <style>
    /* ---------- V1.4 POLISH PASS ---------- */

    .block-container {
        max-width: 1180px;
        padding-top: .8rem;
    }

    .mc-hero {
        padding: 1rem 1.2rem 1.05rem 1.2rem;
        border-radius: 18px;
        min-height: auto;
    }

    .mc-title {
        font-size: clamp(2rem, 4.8vw, 3.35rem);
        letter-spacing: -.045em;
    }

    .mc-subtitle {
        margin-top: .48rem;
        font-size: .95rem;
        line-height: 1.5;
    }

    .mc-section {
        margin-top: 1.2rem;
        margin-bottom: .38rem;
        color: #dfe8ff;
    }

    .nx-module-card {
        min-height: 126px;
        padding: .88rem .95rem;
        border-radius: 16px;
        transition:
            transform .18s ease,
            border-color .18s ease,
            box-shadow .18s ease;
    }

    .nx-module-card:hover {
        transform: translateY(-2px);
        border-color: rgba(126,162,230,.28);
        box-shadow:
            0 18px 44px rgba(0,0,0,.18),
            0 0 32px rgba(68,139,255,.045);
    }

    .nx-big {
        font-size: 1.82rem;
        margin-top: .28rem;
    }

    .nx-label {
        font-size: .84rem;
    }

    .nx-detail {
        font-size: .73rem;
    }

    .stButton > button {
        min-height: 42px;
        border-radius: 12px;
        background:
            linear-gradient(180deg, rgba(16,25,42,.96), rgba(11,18,31,.96));
    }

    .nx-grid-spacer {
        min-height: 1px;
    }

    .nx-pulse {
        position: relative;
        overflow: hidden;
        border-radius: 17px;
        border: 1px solid rgba(58,217,255,.16);
        background:
            radial-gradient(circle at 92% 12%, rgba(169,120,255,.13), transparent 30%),
            linear-gradient(135deg, rgba(12,20,34,.96), rgba(8,14,24,.93));
        padding: .95rem 1rem;
        box-shadow: 0 14px 34px rgba(0,0,0,.14);
        margin-bottom: .75rem;
    }

    .nx-pulse::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg, #3ad9ff, #a978ff, #ff65c8);
    }

    .nx-pulse-kicker {
        color: #58ddff;
        font-size: .66rem;
        font-weight: 950;
        letter-spacing: .16em;
        margin-bottom: .38rem;
    }

    .nx-pulse-copy {
        color: #e7eefc;
        font-size: .93rem;
        line-height: 1.55;
    }

    .nx-money-wrap {
        display:flex;
        align-items:center;
        gap:.9rem;
    }

    .nx-ring {
        --pct: 0;
        --ring-color: #42db82;
        width: 66px;
        height: 66px;
        min-width: 66px;
        border-radius: 50%;
        display:grid;
        place-items:center;
        background:
            conic-gradient(
                var(--ring-color) calc(var(--pct) * 1%),
                rgba(255,255,255,.07) 0
            );
        position:relative;
        box-shadow: 0 0 28px rgba(66,219,130,.09);
    }

    .nx-ring::after {
        content:"";
        position:absolute;
        width:50px;
        height:50px;
        border-radius:50%;
        background:#0a111d;
        border:1px solid rgba(255,255,255,.04);
    }

    .nx-ring-value {
        position:relative;
        z-index:1;
        color:#f8fbff;
        font-size:.82rem;
        font-weight:950;
    }

    .mc-task,
    .mc-radar {
        border-radius: 14px;
        padding: .78rem .9rem;
        margin-bottom: .48rem;
    }

    .mc-task-title {
        font-size: .89rem;
        line-height: 1.32;
    }

    .mc-task-meta {
        font-size: .72rem;
        margin-top: .18rem;
    }

    .nx-panel-title {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:.7rem;
        margin-bottom:.4rem;
    }

    .nx-panel-badge {
        font-size:.62rem;
        letter-spacing:.12em;
        font-weight:900;
        color:#91a0b7;
        border:1px solid rgba(126,162,230,.15);
        border-radius:999px;
        padding:.2rem .45rem;
        background:rgba(10,16,28,.62);
    }

    [data-testid="stSidebar"] .stButton > button {
        min-height: 38px;
    }

    @media (max-width: 700px) {
        .block-container {
            padding-left: .85rem;
            padding-right: .85rem;
        }

        .mc-hero {
            padding: .92rem .95rem 1rem .95rem;
        }

        .mc-title {
            font-size: 2.2rem;
        }

        .nx-module-card {
            min-height: 116px;
        }

        .nx-pulse {
            padding: .85rem .9rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)



st.markdown(
    """
    <style>
    /* ---------- V1.5 BALANCE + QUICK ACCESS ---------- */

    .nx-command-wrap {
        margin-bottom: .25rem;
    }

    .nx-command-wrap .stButton > button {
        margin-top: .1rem;
    }

    .nx-quick-shell {
        border: 1px solid rgba(126,162,230,.14);
        border-radius: 17px;
        background:
            radial-gradient(circle at 88% 14%, rgba(75,146,255,.08), transparent 28%),
            linear-gradient(180deg, rgba(14,22,37,.92), rgba(8,14,24,.90));
        padding: .85rem .9rem .35rem .9rem;
        margin: .15rem 0 .85rem 0;
        box-shadow: 0 14px 34px rgba(0,0,0,.12);
    }

    .nx-quick-label {
        color:#73819a;
        font-size:.64rem;
        font-weight:950;
        letter-spacing:.15em;
        margin-bottom:.55rem;
    }

    .nx-quick-hint {
        color:#78869e;
        font-size:.72rem;
        margin-top:.2rem;
        margin-bottom:.25rem;
    }

    .nx-balanced-card {
        height: 100%;
    }

    .nx-command-row {
        align-items: stretch;
    }

    /* Keep cards/buttons aligned even when only 2 cards are in the row. */
    div[data-testid="column"] > div:has(.nx-module-card) {
        height: 100%;
        display:flex;
        flex-direction:column;
    }

    div[data-testid="column"] > div:has(.nx-module-card) > div[data-testid="stVerticalBlock"] {
        height:100%;
    }

    @media (max-width: 700px) {
        .nx-quick-shell {
            padding: .75rem .75rem .25rem .75rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def page_header(kicker, title, subtitle):
    st.markdown(
        f"""
        <div class="mc-hero">
            <div class="mc-kicker">{kicker}</div>
            <div class="mc-title">{title}</div>
            <div class="mc-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_grid(cards):
    html = '<div class="mc-grid">'
    for color, label, value, detail in cards:
        html += (
            f'<div class="mc-card {color}">'
            f'<div class="mc-label">{label}</div>'
            f'<div class="mc-value">{value}</div>'
            f'<div class="mc-detail">{detail}</div>'
            f'</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# CANVAS — PER VISITOR / SESSION ONLY
# ============================================================

def normalize_canvas_url(url):
    value = (url or "").strip().rstrip("/")
    if value and not value.startswith("http"):
        value = "https://" + value
    return value


def canvas_get(path, params=None):
    canvas = data["canvas"]
    base_url = normalize_canvas_url(canvas.get("base_url"))
    token = canvas.get("token") or ""
    if not base_url or not token:
        raise RuntimeError("Canvas URL or token is missing.")

    response = requests.get(
        base_url + path,
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=20,
    )

    if not response.ok:
        raise RuntimeError(
            f"Canvas HTTP {response.status_code}: {response.text[:180]}"
        )
    return response


def fetch_canvas_assignments():
    courses_resp = canvas_get(
        "/api/v1/courses",
        {
            "enrollment_state": "active",
            "per_page": 100,
        },
    )
    courses = courses_resp.json()

    items = []
    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name") or course.get("course_code") or "Course"
        if not course_id:
            continue

        try:
            assignments_resp = canvas_get(
                f"/api/v1/courses/{course_id}/assignments",
                {
                    "bucket": "upcoming",
                    "order_by": "due_at",
                    "per_page": 100,
                },
            )
            assignments = assignments_resp.json()
        except Exception:
            continue

        for item in assignments:
            due_at = item.get("due_at")
            submitted = False
            if isinstance(item.get("submission"), dict):
                submitted = bool(item["submission"].get("submitted_at"))

            items.append(
                {
                    "id": str(item.get("id") or ""),
                    "course": course_name,
                    "name": item.get("name") or "Assignment",
                    "due_at": due_at,
                    "html_url": item.get("html_url"),
                    "submitted": submitted,
                    "points_possible": item.get("points_possible"),
                    "source": "Canvas",
                }
            )

    items.sort(key=lambda x: x.get("due_at") or "9999")
    return items


def parse_due(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(now_local().tzinfo)
    except Exception:
        return None


def active_school_items():
    items = []
    for item in data["canvas"].get("assignments", []):
        if item.get("submitted"):
            continue
        items.append(item)

    for item in data.get("manual_assignments", []):
        if item.get("done"):
            continue
        due_date = item.get("due_date")
        due_iso = None
        if due_date:
            due_iso = f"{due_date}T23:59:00"
        items.append(
            {
                "id": item.get("id"),
                "course": item.get("course", "Manual"),
                "name": item.get("name", "Assignment"),
                "due_at": due_iso,
                "submitted": False,
                "points_possible": None,
                "source": "Manual",
            }
        )

    items.sort(key=lambda x: x.get("due_at") or "9999")
    return items


# ============================================================
# INTEL
# ============================================================

def mission_stack():
    missions = []

    for item in active_school_items():
        due = parse_due(item.get("due_at"))
        hours = None
        if due:
            hours = (due - now_local()).total_seconds() / 3600

        score = 50
        if hours is not None:
            if hours < 0:
                score = 100
            elif hours <= 24:
                score = 95
            elif hours <= 72:
                score = 82
            elif hours <= 168:
                score = 68

        missions.append(
            {
                "title": item.get("name", "Assignment"),
                "detail": item.get("course", "School"),
                "score": score,
                "type": "School",
                "due": due,
            }
        )

    for task in data.get("tasks", []):
        if task.get("done"):
            continue
        priority = task.get("priority", "Medium")
        score = {"High": 88, "Medium": 64, "Low": 42}.get(priority, 60)
        missions.append(
            {
                "title": task.get("name", "Task"),
                "detail": f"{priority} priority",
                "score": score,
                "type": "Task",
                "due": None,
            }
        )

    enabled = set(enabled_modules())
    focus = data.get("profile", {}).get("primary_goal", "Stay organized")

    focus_module = {
        "Do better in school": "School",
        "Save more money": "Money",
        "Get in better shape": "Fitness",
        "Hit long-term goals": "Intel",
        "Use AI to stay ahead": "Assistant",
    }.get(focus)

    filtered = []
    for mission in missions:
        mission_type = mission.get("type", "")
        module_type = "Intel" if mission_type == "Task" else mission_type

        if module_type in {"School", "Money", "Fitness", "Intel", "Assistant"}:
            if module_type not in enabled:
                continue

        item = dict(mission)
        if focus_module and module_type == focus_module:
            item["score"] = min(100, item.get("score", 0) + 12)

        filtered.append(item)

    filtered.sort(key=lambda x: x["score"], reverse=True)
    return filtered[:8]


def local_brief():
    missions = mission_stack()
    savings = safe_float(data["money"].get("savings"))
    goal = max(safe_float(data["money"].get("goal"), 1), 1)
    savings_pct = min(100, max(0, savings / goal * 100))
    workouts = data["fitness"].get("workouts", [])

    recent_cutoff = now_local().date() - timedelta(days=7)
    recent_workouts = 0
    for workout in workouts:
        try:
            d = date.fromisoformat(workout.get("date", ""))
            if d >= recent_cutoff:
                recent_workouts += 1
        except Exception:
            pass

    if missions:
        lead = missions[0]
        return (
            f"Top priority: {lead['title']} ({lead['detail']}). "
            f"Savings is {savings_pct:.0f}% of target and you've logged "
            f"{recent_workouts} workout{'s' if recent_workouts != 1 else ''} in the last 7 days."
        )

    return (
        f"No urgent missions are stacked right now. Savings is {savings_pct:.0f}% "
        f"of target and you've logged {recent_workouts} workout{'s' if recent_workouts != 1 else ''} "
        "in the last 7 days."
    )


# ============================================================
# OPTIONAL AI — USER SUPPLIES OWN KEY PER SESSION
# ============================================================

def openai_text(prompt, system_text):
    api_key = data["openai"].get("api_key") or ""
    model = data["openai"].get("model") or "gpt-5-mini"

    if not api_key:
        return None, "No OpenAI API key is connected for this session."

    payload = {
        "model": model,
        "instructions": system_text,
        "input": prompt,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        if not response.ok:
            try:
                message = response.json().get("error", {}).get("message")
            except Exception:
                message = response.text[:250]
            return None, f"OpenAI HTTP {response.status_code}: {message}"

        body = response.json()
        for output in body.get("output", []):
            for content in output.get("content", []):
                text = content.get("text")
                if text:
                    return text, None

        return None, "OpenAI returned no text."
    except Exception as exc:
        return None, f"OpenAI connection error: {exc}"


def context_snapshot():
    school = active_school_items()[:12]
    return {
        "school": [
            {
                "course": x.get("course"),
                "name": x.get("name"),
                "due_at": x.get("due_at"),
            }
            for x in school
        ],
        "money": data["money"],
        "fitness": data["fitness"],
        "missions": mission_stack(),
        "intel": data["intel"],
    }


# ============================================================
# ADAPTIVE DASHBOARD HELPERS
# ============================================================

def dashboard_module_order():
    enabled = enabled_modules()
    focus = data.get("profile", {}).get("primary_goal", "Stay organized")

    preferred = {
        "Stay organized": ["Intel", "School", "Money", "Fitness", "Assistant"],
        "Do better in school": ["School", "Intel", "Assistant", "Money", "Fitness"],
        "Save more money": ["Money", "Intel", "Assistant", "School", "Fitness"],
        "Get in better shape": ["Fitness", "Intel", "Assistant", "Money", "School"],
        "Hit long-term goals": ["Intel", "Money", "School", "Fitness", "Assistant"],
        "Use AI to stay ahead": ["Assistant", "Intel", "School", "Money", "Fitness"],
    }.get(
        focus,
        ["Intel", "School", "Money", "Fitness", "Assistant"],
    )

    return [module for module in preferred if module in enabled]


def render_dashboard_snapshot(snap):
    if snap["page"] == "Money":
        try:
            pct = int(str(snap["value"]).replace("%", ""))
        except Exception:
            pct = 0
        pct = max(0, min(100, pct))

        st.markdown(
            f"""
            <div class="nx-module-card green">
                <div class="nx-money-wrap">
                    <div class="nx-ring" style="--pct:{pct};">
                        <div class="nx-ring-value">{pct}%</div>
                    </div>
                    <div>
                        <div class="nx-eye">{snap['eyebrow']}</div>
                        <div class="nx-label">{snap['label']}</div>
                        <div class="nx-detail">{snap['detail']}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="nx-module-card {snap['color']}">
                <div class="nx-eye">{snap['eyebrow']}</div>
                <div class="nx-big">{snap['value']}</div>
                <div class="nx-label">{snap['label']}</div>
                <div class="nx-detail">{snap['detail']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def dashboard_snapshot(module):
    if module == "School":
        items = active_school_items()
        due_soon = 0
        for item in items:
            due = parse_due(item.get("due_at"))
            if due:
                seconds = (due - now_local()).total_seconds()
                if 0 <= seconds <= 7 * 86400:
                    due_soon += 1

        return {
            "color": "purple",
            "eyebrow": "SCHOOL",
            "value": str(len(items)),
            "label": "active assignments",
            "detail": f"{due_soon} due in the next 7 days",
            "page": "School",
        }

    if module == "Money":
        money = data["money"]
        savings = safe_float(money.get("savings"))
        goal = max(safe_float(money.get("goal"), 1), 1)
        pct = min(100, max(0, savings / goal * 100))
        return {
            "color": "green",
            "eyebrow": "MONEY",
            "value": f"{pct:.0f}%",
            "label": "savings target",
            "detail": f"${savings:,.0f} of ${goal:,.0f}",
            "page": "Money",
        }

    if module == "Fitness":
        workouts = data["fitness"].get("workouts", [])
        cutoff = now_local().date() - timedelta(days=7)
        recent = 0
        for workout in workouts:
            try:
                if date.fromisoformat(workout.get("date", "")) >= cutoff:
                    recent += 1
            except Exception:
                pass

        return {
            "color": "pink",
            "eyebrow": "FITNESS",
            "value": str(recent),
            "label": "workouts this week",
            "detail": f"{len(workouts)} total workouts logged",
            "page": "Fitness",
        }

    if module == "Intel":
        radar = data["intel"].get("radar", [])
        captures = data["intel"].get("captures", [])
        open_captures = [item for item in captures if not item.get("done")]
        return {
            "color": "cyan",
            "eyebrow": "INTEL",
            "value": str(len(radar)),
            "label": "future radar items",
            "detail": f"{len(open_captures)} open captures",
            "page": "Intel",
        }

    return {
        "color": "blue",
        "eyebrow": "ASSISTANT",
        "value": "AI",
        "label": "context ready",
        "detail": "Your personal NEXUS assistant",
        "page": "Assistant",
    }


# ============================================================
# FIRST-RUN ONBOARDING
# ============================================================

if not st.session_state.get("nexus_onboarded", False):
    st.markdown(
        """
        <div class="mc-hero">
            <div class="mc-kicker">WELCOME TO NEXUS</div>
            <div class="mc-title">Build your operating system.</div>
            <div class="mc-subtitle">
                Choose what matters to you. NEXUS will shape the dashboard around
                your priorities and you can change everything later.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("nexus_onboarding"):
        onboard_name = st.text_input(
            "What's your name?",
            value=data["profile"].get("name", "") or user_display_name(),
            placeholder="Alex",
        )
        onboard_system = st.text_input(
            "What should your system be called?",
            value=data["profile"].get("system_name", "NEXUS"),
            placeholder="NEXUS",
            help="Examples: NEXUS, ORBIT, CORE, APEX",
        )

        st.markdown("### What do you want NEXUS to manage?")
        default_modules = data["profile"].get(
            "modules",
            ["School", "Money", "Fitness", "Intel", "Assistant"],
        )
        selected_modules = st.multiselect(
            "Choose your modules",
            ["School", "Money", "Fitness", "Intel", "Assistant"],
            default=default_modules,
            help="Your dashboard and navigation will adapt to these choices.",
        )

        primary_goal = st.selectbox(
            "What's your main focus right now?",
            [
                "Stay organized",
                "Do better in school",
                "Save more money",
                "Get in better shape",
                "Hit long-term goals",
                "Use AI to stay ahead",
            ],
            index=0,
        )

        onboard_tz = st.text_input(
            "Timezone",
            value=data["profile"].get("timezone", DEFAULT_TZ),
            help="Example: America/Los_Angeles",
        )

        submitted = st.form_submit_button(
            "BUILD MY NEXUS",
            use_container_width=True,
        )

        if submitted:
            if not selected_modules:
                st.error("Choose at least one module.")
            else:
                data["profile"]["name"] = onboard_name.strip() or user_display_name()
                data["profile"]["system_name"] = onboard_system.strip() or "NEXUS"
                data["profile"]["timezone"] = onboard_tz.strip() or DEFAULT_TZ
                data["profile"]["modules"] = selected_modules
                data["profile"]["primary_goal"] = primary_goal
                data["profile"]["onboarded"] = True
                save_state()
                st.session_state.nexus_onboarded = True
                st.rerun()

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        f'<div class="mc-brand">{system_name()}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Cloud account • personal operating system")

    login_label = user_display_name() or user_email() or "Google account"
    st.caption(f"Signed in as {login_label}")

    for nav_page in PAGES:
        label = f"{PAGE_ICONS[nav_page]}  {nav_page}"
        if st.session_state.current_page == nav_page:
            st.markdown(
                f"""
                <div style="
                    padding:.68rem .8rem;
                    margin:.16rem 0;
                    border-radius:12px;
                    border:1px solid rgba(103,215,255,.40);
                    background:rgba(30,78,120,.28);
                    font-weight:800;
                ">{label}</div>
                """,
                unsafe_allow_html=True,
            )
        else:
            if st.button(label, key=f"nav_{nav_page}", use_container_width=True):
                go_to(nav_page)

    st.divider()

    with st.expander("👤 Profile & cloud account"):
        profile_name = st.text_input(
            "Your name",
            value=data["profile"].get("name", ""),
            key="profile_name",
        )
        profile_system = st.text_input(
            "Name your system",
            value=data["profile"].get("system_name", "NEXUS"),
            placeholder="NEXUS",
            help="Examples: NEXUS, ORBIT, CORE, APEX",
            key="profile_system_name",
        )
        profile_timezone = st.text_input(
            "Timezone",
            value=data["profile"].get("timezone", DEFAULT_TZ),
            help="Example: America/Los_Angeles",
            key="profile_timezone",
        )
        profile_modules = st.multiselect(
            "Active modules",
            ["School", "Money", "Fitness", "Intel", "Assistant"],
            default=data["profile"].get(
                "modules",
                ["School", "Money", "Fitness", "Intel", "Assistant"],
            ),
            key="profile_modules",
        )
        goal_options = [
            "Stay organized",
            "Do better in school",
            "Save more money",
            "Get in better shape",
            "Hit long-term goals",
            "Use AI to stay ahead",
        ]
        current_goal = data["profile"].get("primary_goal", "Stay organized")
        profile_goal = st.selectbox(
            "Primary focus",
            goal_options,
            index=goal_options.index(current_goal) if current_goal in goal_options else 0,
            key="profile_primary_goal",
        )

        if st.button("Save profile", use_container_width=True, key="save_profile"):
            if not profile_modules:
                st.warning("Keep at least one active module.")
            else:
                data["profile"]["name"] = profile_name.strip()
                data["profile"]["system_name"] = profile_system.strip() or "NEXUS"
                data["profile"]["timezone"] = profile_timezone.strip() or DEFAULT_TZ
                data["profile"]["modules"] = profile_modules
                data["profile"]["primary_goal"] = profile_goal
                data["profile"]["onboarded"] = True
                save_state()
                st.success("Saved to NEXUS cloud.")
                st.rerun()

        if st.button("Log out", use_container_width=True, key="logout_nexus"):
            # Clear user-specific in-memory state before removing auth cookie.
            for key in [
                "public_data",
                "nexus_loaded_uid",
                "nexus_existing_user",
                "nexus_onboarded",
                "current_page",
            ]:
                st.session_state.pop(key, None)
            st.logout()

    with st.expander("💾 Backup / restore"):
        backup_text = json.dumps(data, indent=2, default=str)
        st.download_button(
            "Download my data",
            backup_text,
            file_name="nexus-backup.json",
            mime="application/json",
            use_container_width=True,
        )

        uploaded_backup = st.file_uploader(
            "Restore JSON backup",
            type=["json"],
            key="backup_upload",
        )
        if uploaded_backup is not None:
            try:
                restored = json.loads(uploaded_backup.getvalue().decode("utf-8"))
                if isinstance(restored, dict):
                    st.session_state.public_data = merge_with_defaults(restored)
                    data = st.session_state.public_data
                    data["profile"]["onboarded"] = True
                    save_state()
                    st.success("Backup restored and saved to NEXUS cloud.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not restore backup: {exc}")

    if st.session_state.get("cloud_save_error"):
        st.warning(st.session_state["cloud_save_error"])
    else:
        st.caption("☁️ Cloud sync active")

    st.caption(APP_VERSION)


# ============================================================
# DASHBOARD
# ============================================================

page = st.session_state.current_page

def quick_access_pages():
    ordered = dashboard_module_order()
    return [page for page in ordered if page in PAGES]


def balanced_command_rows(snapshots):
    rows = []
    for start in range(0, len(snapshots), 3):
        rows.append(snapshots[start:start + 3])
    return rows


if page == "Dashboard":
    name = data["profile"].get("name", "").strip()
    greeting = f"Welcome back, {name}." if name else "Your personal operating system."
    focus = data.get("profile", {}).get("primary_goal", "Stay organized")

    page_header(
        "NEXUS // COMMAND CENTER",
        system_name(),
        f"{greeting} Current focus: {focus}.",
    )

    modules = dashboard_module_order()
    missions = mission_stack()
    snapshots = [dashboard_snapshot(module) for module in modules]

    # --------------------------------------------------------
    # QUICK ACCESS
    # --------------------------------------------------------
    st.markdown(
        '<div class="mc-section">QUICK ACCESS</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="nx-quick-shell">
            <div class="nx-quick-label">JUMP TO</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_pages = quick_access_pages()
    quick_cols = st.columns(5)

    for idx in range(5):
        with quick_cols[idx]:
            if idx < len(quick_pages):
                target = quick_pages[idx]
                icon = {
                    "School": "🎓",
                    "Money": "💰",
                    "Fitness": "🏋️",
                    "Intel": "🧠",
                    "Assistant": "✦",
                }.get(target, "→")

                if st.button(
                    f"{icon} {target}",
                    key=f"quick_{target}",
                    use_container_width=True,
                ):
                    go_to(target)
            else:
                st.write("")

    action_cols = st.columns([1, 1, 1, 2])

    with action_cols[0]:
        if module_enabled("Intel"):
            if st.button(
                "＋ Quick Capture",
                key="quick_capture_jump",
                use_container_width=True,
            ):
                go_to("Intel")

    with action_cols[1]:
        if module_enabled("School"):
            if st.button(
                "＋ Assignment",
                key="quick_assignment_jump",
                use_container_width=True,
            ):
                go_to("School")

    with action_cols[2]:
        if module_enabled("Fitness"):
            if st.button(
                "＋ Workout",
                key="quick_workout_jump",
                use_container_width=True,
            ):
                go_to("Fitness")

    with action_cols[3]:
        st.caption("Fast actions open the right NEXUS module so you can add the item immediately.")

    # --------------------------------------------------------
    # COMMAND DECK
    # --------------------------------------------------------
    st.markdown(
        '<div class="mc-section">COMMAND DECK</div>',
        unsafe_allow_html=True,
    )

    rows = balanced_command_rows(snapshots)

    for row_index, row in enumerate(rows):
        # If the final row has 2 cards, center them instead of leaving a dead third slot.
        if len(row) == 2:
            outer = st.columns([.5, 1, 1, .5])
            card_columns = [outer[1], outer[2]]
        elif len(row) == 1:
            outer = st.columns([1, 1.35, 1])
            card_columns = [outer[1]]
        else:
            card_columns = st.columns(3)

        for idx, snap in enumerate(row):
            with card_columns[idx]:
                st.markdown(
                    '<div class="nx-command-wrap">',
                    unsafe_allow_html=True,
                )

                render_dashboard_snapshot(snap)

                if st.button(
                    f"Open {snap['page']}",
                    key=f"dash_open_{row_index}_{snap['page']}",
                    use_container_width=True,
                ):
                    go_to(snap["page"])

                st.markdown("</div>", unsafe_allow_html=True)

    # --------------------------------------------------------
    # NEXUS PULSE
    # --------------------------------------------------------
    st.markdown(
        '<div class="mc-section">NEXUS PULSE</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="nx-pulse">
            <div class="nx-pulse-kicker">LIVE READOUT</div>
            <div class="nx-pulse-copy">{local_brief()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.12, .88])

    with left:
        st.markdown(
            """
            <div class="nx-panel-title">
                <div class="mc-section" style="margin-top:0;">MISSION STACK</div>
                <div class="nx-panel-badge">PRIORITY QUEUE</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not missions:
            st.info("Nothing urgent is stacked right now.")
        else:
            for item in missions[:6]:
                due_text = ""
                if item.get("due"):
                    due_text = item["due"].strftime("%a %b %-d • %-I:%M %p")

                meta = f"{item['type']} • {item['detail']}"
                if due_text:
                    meta += f" • {due_text}"

                st.markdown(
                    f"""
                    <div class="mc-task">
                        <div class="mc-task-title">{item['title']}</div>
                        <div class="mc-task-meta">{meta}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with right:
        if module_enabled("Intel"):
            st.markdown(
                """
                <div class="nx-panel-title">
                    <div class="mc-section" style="margin-top:0;">FUTURE RADAR</div>
                    <div class="nx-panel-badge">AHEAD</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            radar = sorted(
                data["intel"].get("radar", []),
                key=lambda x: x.get("date", "9999"),
            )

            if not radar:
                st.caption("No future radar items yet.")
            else:
                for item in radar[:5]:
                    try:
                        target = date.fromisoformat(item["date"])
                        days = (target - now_local().date()).days
                        when = f"{days} days" if days >= 0 else f"{abs(days)} days ago"
                    except Exception:
                        when = item.get("date", "")

                    st.markdown(
                        f"""
                        <div class="mc-radar">
                            <div class="mc-task-title">{item.get('name', 'Event')}</div>
                            <div class="mc-task-meta">{when}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                """
                <div class="nx-panel-title">
                    <div class="mc-section" style="margin-top:0;">CURRENT FOCUS</div>
                    <div class="nx-panel-badge">NOW</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="nx-pulse"><div class="nx-pulse-copy">{focus}</div></div>',
                unsafe_allow_html=True,
            )


# ============================================================
# SCHOOL
# ============================================================

elif page == "School":
    page_header(
        "Academics",
        "SCHOOL // COMMAND",
        "Connect your own Canvas account for this browser session, or use the manual assignment planner.",
    )

    tab1, tab2 = st.tabs(["Canvas", "Manual planner"])

    with tab1:
        st.warning(
            "Public-safe mode: your Canvas URL/token live only in this Streamlit session. "
            "They are not written to a file by this app."
        )

        c1, c2 = st.columns([1.1, 1])
        with c1:
            data["canvas"]["base_url"] = st.text_input(
                "Canvas URL",
                value=data["canvas"].get("base_url", ""),
                placeholder="https://school.instructure.com",
            )
        with c2:
            data["canvas"]["token"] = st.text_input(
                "Canvas access token",
                value=data["canvas"].get("token", ""),
                type="password",
            )

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Connect + sync", use_container_width=True):
                try:
                    with st.spinner("Syncing Canvas..."):
                        assignments = fetch_canvas_assignments()
                    data["canvas"]["assignments"] = assignments
                    data["canvas"]["connected"] = True
                    data["canvas"]["error"] = None
                    data["canvas"]["last_sync"] = now_local().isoformat()
                    save_state()
                    st.success(f"Connected. Loaded {len(assignments)} upcoming assignments.")
                except Exception as exc:
                    data["canvas"]["connected"] = False
                    data["canvas"]["error"] = str(exc)
                    st.error(str(exc))

        with b2:
            if st.button("Disconnect Canvas", use_container_width=True):
                data["canvas"] = default_state()["canvas"]
                save_state()
                st.rerun()

        if data["canvas"].get("connected"):
            st.success("Canvas connected for this session.")
            if data["canvas"].get("last_sync"):
                st.caption(f"Last sync: {data['canvas']['last_sync']}")
        elif data["canvas"].get("error"):
            st.error(data["canvas"]["error"])

        items = [
            x for x in data["canvas"].get("assignments", [])
            if not x.get("submitted")
        ]

        st.markdown('<div class="mc-section">Upcoming Canvas work</div>', unsafe_allow_html=True)
        if not items:
            st.info("No synced assignments yet.")
        else:
            for item in items[:30]:
                due = parse_due(item.get("due_at"))
                due_text = due.strftime("%a %b %-d • %-I:%M %p") if due else "No due date"
                st.markdown(
                    f"""
                    <div class="mc-task">
                        <div class="mc-task-title">{item.get('name','Assignment')}</div>
                        <div class="mc-task-meta">{item.get('course','Course')} • {due_text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with tab2:
        with st.form("manual_assignment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                course = st.text_input("Course")
                assignment = st.text_input("Assignment")
            with c2:
                due_date = st.date_input("Due date", value=now_local().date())
                priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)

            if st.form_submit_button("Add assignment", use_container_width=True):
                if assignment.strip():
                    data["manual_assignments"].append(
                        {
                            "id": f"manual-{datetime.now().timestamp()}",
                            "course": course.strip() or "Manual",
                            "name": assignment.strip(),
                            "due_date": due_date.isoformat(),
                            "priority": priority,
                            "done": False,
                        }
                    )
                    save_state()
                    st.rerun()

        for idx, item in enumerate(data.get("manual_assignments", [])):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"{item.get('name')}  \n"
                    f"{item.get('course')} • due {item.get('due_date')} • {item.get('priority')}"
                )
            with c2:
                if not item.get("done"):
                    if st.button("Done", key=f"manual_done_{idx}", use_container_width=True):
                        item["done"] = True
                        save_state()
                        st.rerun()
                else:
                    st.caption("✓ Done")


# ============================================================
# MONEY
# ============================================================

elif page == "Money":
    page_header(
        "Finance",
        "MONEY // TRACKER",
        "Simple savings, income, and expense tracking. Data is private to this browser session unless you export a backup.",
    )

    money = data["money"]

    c1, c2 = st.columns(2)
    with c1:
        money["savings"] = st.number_input(
            "Current savings",
            min_value=0.0,
            value=float(money.get("savings", 0.0)),
            step=25.0,
        )
    with c2:
        money["goal"] = st.number_input(
            "Savings goal",
            min_value=1.0,
            value=float(money.get("goal", 5000.0)),
            step=100.0,
        )
    save_state()

    savings = safe_float(money["savings"])
    goal = max(safe_float(money["goal"], 1), 1)
    pct = min(100, max(0, savings / goal * 100))

    cards = [
        ("green", "Savings", f"${savings:,.0f}", "current balance"),
        ("cyan", "Goal", f"${goal:,.0f}", "target"),
        ("purple", "Progress", f"{pct:.1f}%", "toward goal"),
        ("orange", "Remaining", f"${max(goal-savings,0):,.0f}", "to target"),
    ]
    card_grid(cards)
    st.progress(pct / 100)

    st.markdown('<div class="mc-section">Cash flow</div>', unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        with st.form("income_form", clear_on_submit=True):
            st.markdown("#### Add income")
            label = st.text_input("Source", key="income_label")
            amount = st.number_input("Amount", min_value=0.0, step=10.0, key="income_amount")
            if st.form_submit_button("Add income", use_container_width=True):
                if amount > 0:
                    money["income"].append(
                        {
                            "date": now_local().date().isoformat(),
                            "label": label.strip() or "Income",
                            "amount": float(amount),
                        }
                    )
                    save_state()
                    st.rerun()

    with right:
        with st.form("expense_form", clear_on_submit=True):
            st.markdown("#### Add expense")
            label = st.text_input("Description", key="expense_label")
            amount = st.number_input("Amount", min_value=0.0, step=10.0, key="expense_amount")
            if st.form_submit_button("Add expense", use_container_width=True):
                if amount > 0:
                    money["expenses"].append(
                        {
                            "date": now_local().date().isoformat(),
                            "label": label.strip() or "Expense",
                            "amount": float(amount),
                        }
                    )
                    save_state()
                    st.rerun()

    total_income = sum(safe_float(x.get("amount")) for x in money["income"])
    total_expenses = sum(safe_float(x.get("amount")) for x in money["expenses"])
    net = total_income - total_expenses

    m1, m2, m3 = st.columns(3)
    m1.metric("Tracked income", f"${total_income:,.2f}")
    m2.metric("Tracked expenses", f"${total_expenses:,.2f}")
    m3.metric("Net tracked", f"${net:,.2f}")


# ============================================================
# FITNESS
# ============================================================

elif page == "Fitness":
    page_header(
        "Performance",
        "FITNESS // LAB",
        "Track bodyweight, workouts, and consistency without tying the public app to any private device.",
    )

    fit = data["fitness"]

    c1, c2 = st.columns(2)
    with c1:
        current_weight = st.number_input(
            "Current weight",
            min_value=0.0,
            value=float(fit.get("weight") or 0.0),
            step=0.5,
        )
    with c2:
        goal_weight = st.number_input(
            "Goal weight",
            min_value=0.0,
            value=float(fit.get("goal_weight") or 0.0),
            step=0.5,
        )

    if current_weight > 0:
        fit["weight"] = current_weight
    if goal_weight > 0:
        fit["goal_weight"] = goal_weight
    save_state()

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Log today's weight", use_container_width=True):
            if current_weight > 0:
                fit["history"].append(
                    {
                        "date": now_local().date().isoformat(),
                        "weight": float(current_weight),
                    }
                )
                save_state()
                st.success("Weight logged.")

    with b2:
        workout_name = st.text_input("Workout label", placeholder="Push / Pull / Legs / Run")
        if st.button("Log workout", use_container_width=True):
            if workout_name.strip():
                fit["workouts"].append(
                    {
                        "date": now_local().date().isoformat(),
                        "name": workout_name.strip(),
                    }
                )
                save_state()
                st.rerun()

    cutoff = now_local().date() - timedelta(days=7)
    last7 = 0
    for w in fit["workouts"]:
        try:
            if date.fromisoformat(w["date"]) >= cutoff:
                last7 += 1
        except Exception:
            pass

    delta = None
    if fit.get("weight") and fit.get("goal_weight"):
        delta = fit["goal_weight"] - fit["weight"]

    cards = [
        ("pink", "Current", f"{fit.get('weight') or '—'}", "bodyweight"),
        ("purple", "Goal", f"{fit.get('goal_weight') or '—'}", "target"),
        ("green", "7 Day", str(last7), "workouts"),
        ("cyan", "To Goal", f"{delta:+.1f}" if delta is not None else "—", "weight delta"),
    ]
    card_grid(cards)

    st.markdown('<div class="mc-section">Recent workouts</div>', unsafe_allow_html=True)
    for workout in fit["workouts"][-12:][::-1]:
        st.markdown(
            f"""
            <div class="mc-task">
                <div class="mc-task-title">{workout.get('name','Workout')}</div>
                <div class="mc-task-meta">{workout.get('date')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# INTEL
# ============================================================

elif page == "Intel":
    page_header(
        "Personal Radar",
        f"{system_name()} // INTEL",
        "One place for priorities, future dates, quick capture, and the information you actually need to act on.",
    )

    tabs = st.tabs(["Mission Stack", "Future Radar", "Quick Capture"])

    with tabs[0]:
        with st.form("task_form", clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                task_name = st.text_input("New mission")
            with c2:
                priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            if st.form_submit_button("Add mission", use_container_width=True):
                if task_name.strip():
                    data["tasks"].append(
                        {
                            "name": task_name.strip(),
                            "priority": priority,
                            "done": False,
                        }
                    )
                    save_state()
                    st.rerun()

        missions = mission_stack()
        if not missions:
            st.info("No active missions.")
        else:
            for item in missions:
                st.markdown(
                    f"""
                    <div class="mc-task">
                        <div class="mc-task-title">{item['title']}</div>
                        <div class="mc-task-meta">{item['type']} • {item['detail']} • score {item['score']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("#### Personal tasks")
        for idx, task in enumerate(data["tasks"]):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.write(f"{'~~' if task.get('done') else ''}{task.get('name')}{'~~' if task.get('done') else ''}")
                st.caption(task.get("priority", "Medium"))
            with c2:
                if st.button("✓", key=f"taskdone_{idx}", use_container_width=True):
                    task["done"] = not task.get("done", False)
                    save_state()
                    st.rerun()

    with tabs[1]:
        with st.form("radar_form", clear_on_submit=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                radar_name = st.text_input("Event / goal / deadline")
            with c2:
                radar_date = st.date_input("Date", value=now_local().date() + timedelta(days=30))
            if st.form_submit_button("Add to radar", use_container_width=True):
                if radar_name.strip():
                    data["intel"]["radar"].append(
                        {
                            "name": radar_name.strip(),
                            "date": radar_date.isoformat(),
                        }
                    )
                    save_state()
                    st.rerun()

        radar = sorted(data["intel"]["radar"], key=lambda x: x.get("date", "9999"))
        for idx, item in enumerate(radar):
            try:
                target = date.fromisoformat(item["date"])
                days = (target - now_local().date()).days
                when = f"{days} days away" if days >= 0 else f"{abs(days)} days ago"
            except Exception:
                when = item.get("date")

            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"""
                    <div class="mc-radar">
                        <strong>{item.get('name')}</strong><br>
                        <span style="color:#91a0ba">{item.get('date')} • {when}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Remove", key=f"radar_remove_{idx}", use_container_width=True):
                    data["intel"]["radar"].remove(item)
                    save_state()
                    st.rerun()

    with tabs[2]:
        capture = st.text_area(
            "Dump anything here",
            placeholder="Idea, reminder, thought, link, something you don't want to lose...",
            height=120,
        )
        if st.button("Capture", use_container_width=True):
            if capture.strip():
                data["intel"]["captures"].append(
                    {
                        "created_at": now_local().isoformat(),
                        "text": capture.strip(),
                    }
                )
                save_state()
                st.rerun()

        for item in data["intel"]["captures"][-20:][::-1]:
            st.markdown(
                f"""
                <div class="mc-task">
                    <div class="mc-task-title">{item.get('text')}</div>
                    <div class="mc-task-meta">{item.get('created_at')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================
# ASSISTANT
# ============================================================

elif page == "Assistant":
    page_header(
        "Intelligence",
        f"ASK // {system_name()}",
        "A contextual assistant for your personal system. It can use your session data locally, or your own OpenAI API key if you choose.",
    )

    with st.expander("Optional OpenAI connection"):
        st.caption(
            "Use your own API key. This public build stores it only in this Streamlit session and does not write it to disk."
        )
        data["openai"]["api_key"] = st.text_input(
            "OpenAI API key",
            value=data["openai"].get("api_key", ""),
            type="password",
            key="public_openai_key",
        )
        data["openai"]["model"] = st.text_input(
            "Model",
            value=data["openai"].get("model", "gpt-5-mini"),
            key="public_openai_model",
        )
        save_state()

    st.markdown('<div class="mc-section">Current readout</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mc-note">{local_brief()}</div>', unsafe_allow_html=True)

    history = data.setdefault("assistant_history", [])

    for msg in history[-12:]:
        with st.chat_message(msg.get("role", "assistant")):
            st.markdown(msg.get("content", ""))

    prompt = st.chat_input(f"Ask {system_name()} what matters right now...")

    if prompt:
        history.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if data["openai"].get("api_key"):
                system = (
                    f"You are {system_name()}, a concise personal operations assistant inside a public Streamlit app. "
                    "Use the supplied context to help the user prioritize school, money, fitness, goals, and tasks. "
                    "Do not claim access to devices, private accounts, or controls. "
                    "Be practical and concise."
                )
                context = json.dumps(context_snapshot(), default=str)
                answer, error = openai_text(
                    f"USER QUESTION:\n{prompt}\n\nCURRENT APP CONTEXT:\n{context}",
                    system,
                )
                if error:
                    answer = f"{local_brief()}\n\nAI connection issue: {error}"
            else:
                lower = prompt.lower()
                missions = mission_stack()
                if "next" in lower or "what should" in lower or "priority" in lower:
                    if missions:
                        top = missions[0]
                        answer = (
                            f"Your next move is {top['title']} — {top['detail']}. "
                            f"It currently has the highest mission score ({top['score']})."
                        )
                    else:
                        answer = "You have no urgent missions stacked right now."
                elif "money" in lower or "saving" in lower:
                    savings = safe_float(data["money"].get("savings"))
                    goal = max(safe_float(data["money"].get("goal"), 1), 1)
                    answer = (
                        f"You're at ${savings:,.0f} / ${goal:,.0f} "
                        f"({min(100, savings/goal*100):.1f}% of goal)."
                    )
                elif "workout" in lower or "fitness" in lower:
                    answer = (
                        f"You've logged {len(data['fitness'].get('workouts', []))} total workouts "
                        "in this session profile."
                    )
                else:
                    answer = (
                        local_brief()
                        + "\n\nConnect your own OpenAI API key above if you want broader natural-language reasoning."
                    )

            st.markdown(answer)

        history.append({"role": "assistant", "content": answer})
        data["assistant_history"] = history[-40:]
        save_state()

    if history:
        if st.button("Clear conversation"):
            data["assistant_history"] = []
            save_state()
            st.rerun()


# ============================================================
# PUBLIC SAFETY FOOTER
# ============================================================

st.divider()
st.caption(
    f"{system_name()} • NEXUS Polished Command Center • Google login + private Neon persistence • "
    "no owner Canvas token, and no owner OpenAI key are included in this build."
)
