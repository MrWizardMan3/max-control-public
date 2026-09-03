
import json
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="MAX // CONTROL — Public",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "PUBLIC V1.0"
DEFAULT_TZ = "America/Los_Angeles"

PAGES = [
    "Dashboard",
    "School",
    "Money",
    "Fitness",
    "Intel",
    "Assistant",
]

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
            "timezone": DEFAULT_TZ,
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


if "public_data" not in st.session_state:
    st.session_state.public_data = default_state()

if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

data = st.session_state.public_data


def save_state():
    st.session_state.public_data = data


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

    missions.sort(key=lambda x: x["score"], reverse=True)
    return missions[:8]


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
            f"Top priority: **{lead['title']}** ({lead['detail']}). "
            f"Savings is **{savings_pct:.0f}%** of target and you've logged "
            f"**{recent_workouts} workout{'s' if recent_workouts != 1 else ''}** in the last 7 days."
        )

    return (
        f"No urgent missions are stacked right now. Savings is **{savings_pct:.0f}%** "
        f"of target and you've logged **{recent_workouts} workout{'s' if recent_workouts != 1 else ''}** "
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
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown('<div class="mc-brand">MAX // CONTROL</div>', unsafe_allow_html=True)
    st.caption("Public build • no device controls")

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

    with st.expander("👤 Session profile"):
        data["profile"]["name"] = st.text_input(
            "Name",
            value=data["profile"].get("name", ""),
            key="profile_name",
        )
        data["profile"]["timezone"] = st.text_input(
            "Timezone",
            value=data["profile"].get("timezone", DEFAULT_TZ),
            help="Example: America/Los_Angeles",
            key="profile_timezone",
        )
        save_state()

    with st.expander("💾 Backup / restore"):
        backup_text = json.dumps(data, indent=2, default=str)
        st.download_button(
            "Download my data",
            backup_text,
            file_name="max-control-backup.json",
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
                    st.session_state.public_data = restored
                    st.success("Backup restored.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not restore backup: {exc}")

    st.caption(APP_VERSION)


# ============================================================
# DASHBOARD
# ============================================================

page = st.session_state.current_page

if page == "Dashboard":
    name = data["profile"].get("name", "").strip()
    greeting = f"Welcome back, {name}." if name else "Your command center."

    page_header(
        "Personal Operating System",
        "MAX // CONTROL",
        f"{greeting} Public-safe build with school, money, fitness, intel, and AI — no computer controls.",
    )

    school_items = active_school_items()
    missions = mission_stack()
    money = data["money"]
    savings = safe_float(money.get("savings"))
    goal = max(safe_float(money.get("goal"), 1), 1)
    pct = min(100, max(0, savings / goal * 100))

    workouts = data["fitness"].get("workouts", [])
    cutoff = now_local().date() - timedelta(days=7)
    last7 = 0
    for w in workouts:
        try:
            if date.fromisoformat(w.get("date", "")) >= cutoff:
                last7 += 1
        except Exception:
            pass

    cards = [
        ("purple", "School", str(len(school_items)), "active assignments"),
        ("green", "Savings", f"{pct:.0f}%", f"${savings:,.0f} of ${goal:,.0f}"),
        ("pink", "Fitness", str(last7), "workouts in last 7 days"),
        ("cyan", "Mission Stack", str(len(missions)), "active priorities"),
    ]
    card_grid(cards)

    st.markdown('<div class="mc-section">✦ MAX PULSE</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mc-note">{local_brief()}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1.15, 0.85])

    with col1:
        st.markdown('<div class="mc-section">Top missions</div>', unsafe_allow_html=True)
        if not missions:
            st.info("Nothing urgent yet. Add assignments, tasks, or radar items.")
        else:
            for item in missions[:5]:
                due_text = ""
                if item.get("due"):
                    due_text = item["due"].strftime("%a %b %-d • %-I:%M %p")
                st.markdown(
                    f"""
                    <div class="mc-task">
                        <div class="mc-task-title">{item['title']}</div>
                        <div class="mc-task-meta">{item['type']} • {item['detail']}
                        {f' • {due_text}' if due_text else ''} • score {item['score']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col2:
        st.markdown('<div class="mc-section">Future radar</div>', unsafe_allow_html=True)
        radar = sorted(
            data["intel"].get("radar", []),
            key=lambda x: x.get("date", "9999"),
        )
        if not radar:
            st.caption("Add future dates in Intel.")
        else:
            for item in radar[:4]:
                try:
                    target = date.fromisoformat(item["date"])
                    days = (target - now_local().date()).days
                    when = f"{days} days" if days >= 0 else f"{abs(days)} days ago"
                except Exception:
                    when = item.get("date", "")
                st.markdown(
                    f"""
                    <div class="mc-radar">
                        <strong>{item.get('name','Event')}</strong><br>
                        <span style="color:#91a0ba">{when}</span>
                    </div>
                    """,
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
                    f"**{item.get('name')}**  \n"
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
        "MAX // INTEL",
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
        "ASK // MAX",
        "A contextual assistant for the public build. It can use your session data locally, or your own OpenAI API key if you choose.",
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

    prompt = st.chat_input("Ask MAX what matters right now...")

    if prompt:
        history.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if data["openai"].get("api_key"):
                system = (
                    "You are MAX, a concise personal operations assistant inside a public Streamlit app. "
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
                            f"Your next move is **{top['title']}** — {top['detail']}. "
                            f"It currently has the highest mission score ({top['score']})."
                        )
                    else:
                        answer = "You have no urgent missions stacked right now."
                elif "money" in lower or "saving" in lower:
                    savings = safe_float(data["money"].get("savings"))
                    goal = max(safe_float(data["money"].get("goal"), 1), 1)
                    answer = (
                        f"You're at **${savings:,.0f} / ${goal:,.0f}** "
                        f"({min(100, savings/goal*100):.1f}% of goal)."
                    )
                elif "workout" in lower or "fitness" in lower:
                    answer = (
                        f"You've logged **{len(data['fitness'].get('workouts', []))} total workouts** "
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
    "MAX // CONTROL Public • No Mac/PC control endpoints, no shared data.json, "
    "no owner Canvas token, and no owner OpenAI key are included in this build."
)
