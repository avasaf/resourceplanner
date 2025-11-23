import sqlite3
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = "schedule.db"

# ---------- Styling ----------

# Core brand tones provided by the design guide
PALETTE = {
    "primary": "#0B1E41",  # Quantum Blue
    "background": "#FFFFFF",  # Infinity White
    "accent": "#64A6D9",  # Inspired by Motion tones
    "muted": "#C6DEB3",  # Inspired by Strata tones
    "highlight": "#C46565",  # Pulse inspired
}

STATUS_COLORS = {
    "Planned": "#64A6D9",
    "In Progress": "#8BC0B5",
    "Done": "#0B1E41",
    "On Hold": "#FADCCE",
    "Holiday": "#C46565",
    "Time Off": "#C46565",
}

STATUS_OPTIONS = list(STATUS_COLORS.keys())


def inject_styles():
    """Apply a modern layout and brand colors."""

    st.markdown(
        f"""
        <style>
        :root {{
            --primary-color: {PALETTE['primary']};
            --secondary-background-color: #F5F7FB;
            --text-color: #1B263B;
            --font: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        }}
        .main > div {{
            background: linear-gradient(180deg, {PALETTE['background']} 0%, #F5F7FB 35%, #E9F2FF 100%);
            color: #1B263B;
        }}
        .sidebar .sidebar-content {{
            background: {PALETTE['primary']};
        }}
        .sidebar .sidebar-content * {{ color: {PALETTE['background']}; }}
        .stButton button {{
            background: {PALETTE['primary']};
            color: {PALETTE['background']};
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: 600;
        }}
        .stButton button:hover {{
            background: {PALETTE['accent']};
            color: {PALETTE['primary']};
            transition: all 0.2s ease-in-out;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-weight: 700;
            color: {PALETTE['primary']};
        }}
        .metric-card {{
            background: {PALETTE['background']};
            border: 1px solid #E0E7F1;
            padding: 1rem;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(11, 30, 65, 0.08);
        }}
        .pill {{
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 12px;
            color: {PALETTE['background']};
        }}
        .section-card {{
            background: {PALETTE['background']};
            border: 1px solid #E0E7F1;
            border-radius: 14px;
            padding: 1rem 1.25rem;
            box-shadow: 0 10px 30px rgba(11, 30, 65, 0.06);
        }}
        /* Input focus and checkbox accents */
        input, textarea, select, .stDateInput input {{
            border-radius: 8px !important;
        }}
        .stDateInput > div > div > input:focus,
        .stMultiSelect > div > div > input:focus,
        .stTextInput > div > div > input:focus {{
            border: 1px solid {PALETTE['accent']} !important;
            box-shadow: 0 0 0 2px {PALETTE['accent']}22 !important;
        }}
        .st-multi-select__tag {{
            background: {PALETTE['accent']}22 !important;
            color: {PALETTE['primary']} !important;
        }}
        .stRadio > div[role="radiogroup"] label span {{
            color: {PALETTE['primary']} !important;
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------- DB helpers ----------

def get_connection():
    """Return a sqlite3 connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            color TEXT,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Planned',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(resource_id) REFERENCES resources(id)
        )
    """)

    conn.commit()
    conn.close()


def seed_demo_data():
    """Seed the database with demo vessels, projects, people, and tasks in idempotent fashion."""

    demo_resources = [
        {"name": "Aurora Explorer", "type": "Vessel", "color": "#0B1E41"},
        {"name": "Nordic Surveyor", "type": "Vessel", "color": "#64A6D9"},
        {"name": "Project Polaris", "type": "Project", "color": "#8BC0B5"},
        {"name": "Project Horizon", "type": "Project", "color": "#C46565"},
        {"name": "Alex Morgan", "type": "Person", "color": "#0B1E41"},
        {"name": "Sam Lee", "type": "Person", "color": "#64A6D9"},
        {"name": "Priya Nair", "type": "Person", "color": "#8BC0B5"},
    ]

    demo_tasks = [
        ("Aurora Explorer", "Cable lay - North Sea", "Laying subsea cables", "2025-01-04", "2025-01-15", "In Progress"),
        ("Nordic Surveyor", "ROV inspection", "Inspection and survey", "2025-01-10", "2025-01-18", "Planned"),
        ("Project Polaris", "Mobilisation", "Prep and mobilisation", "2025-01-05", "2025-01-08", "Planned"),
        ("Project Polaris", "Execution phase", "Main work package", "2025-01-20", "2025-02-05", "In Progress"),
        ("Project Horizon", "Design freeze", "Final design and sign-off", "2025-01-12", "2025-01-17", "On Hold"),
        ("Alex Morgan", "Holiday", "Winter break", "2025-01-24", "2025-01-31", "Holiday"),
        ("Alex Morgan", "Deck lead", "Oversee deck operations", "2025-02-10", "2025-02-22", "Planned"),
        ("Sam Lee", "Time off", "Personal leave", "2025-02-03", "2025-02-07", "Time Off"),
        ("Sam Lee", "Project Polaris support", "Site engineering", "2025-01-14", "2025-01-22", "In Progress"),
        ("Priya Nair", "HSE training", "Annual certification", "2025-01-16", "2025-01-18", "Done"),
        ("Priya Nair", "Project Horizon coordination", "PMO support", "2025-02-01", "2025-02-12", "Planned"),
    ]

    conn = get_connection()
    c = conn.cursor()

    name_to_id = {}
    for res in demo_resources:
        c.execute(
            "SELECT id FROM resources WHERE name = ? AND type = ?",
            (res["name"], res["type"]),
        )
        row = c.fetchone()
        if row:
            res_id = row[0]
            c.execute(
                "UPDATE resources SET active = 1, color = ? WHERE id = ?",
                (res["color"], res_id),
            )
        else:
            c.execute(
                "INSERT INTO resources (name, type, color, active) VALUES (?, ?, ?, 1)",
                (res["name"], res["type"], res.get("color")),
            )
            res_id = c.lastrowid
        name_to_id[res["name"]] = res_id

    now = datetime.utcnow().isoformat()
    for res_name, title, desc, start, end, status in demo_tasks:
        res_id = name_to_id.get(res_name)
        if not res_id:
            continue
        c.execute(
            """
            SELECT id FROM tasks
            WHERE resource_id = ? AND title = ? AND start_date = ? AND end_date = ?
            """,
            (res_id, title, start, end),
        )
        exists = c.fetchone()
        if exists:
            continue
        c.execute(
            """
            INSERT INTO tasks (resource_id, title, description, start_date, end_date, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (res_id, title, desc, start, end, status, now, now),
        )

    conn.commit()
    conn.close()


def fetch_resources(active_only=True):
    """Return list of resources as dicts."""
    conn = get_connection()
    c = conn.cursor()
    if active_only:
        c.execute("SELECT * FROM resources WHERE active = 1 ORDER BY type, name")
    else:
        c.execute("SELECT * FROM resources ORDER BY type, name")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_tasks(resource_id=None):
    """Return list of tasks joined with resource info as dicts."""
    conn = get_connection()
    c = conn.cursor()
    if resource_id:
        c.execute("""
            SELECT t.*, r.name AS resource_name, r.type AS resource_type, r.color AS resource_color
            FROM tasks t
            JOIN resources r ON t.resource_id = r.id
            WHERE t.resource_id = ?
            ORDER BY start_date
        """, (resource_id,))
    else:
        c.execute("""
            SELECT t.*, r.name AS resource_name, r.type AS resource_type, r.color AS resource_color
            FROM tasks t
            JOIN resources r ON t.resource_id = r.id
            ORDER BY start_date
        """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_tasks_with_resources():
    """Convenience helper returning tasks joined to resource metadata as a DataFrame."""

    tasks = fetch_tasks()
    if not tasks:
        return pd.DataFrame()

    tasks_df = pd.DataFrame(tasks)
    tasks_df["Start"] = pd.to_datetime(tasks_df["start_date"])
    tasks_df["Finish"] = pd.to_datetime(tasks_df["end_date"])
    return tasks_df


def expand_tasks_to_calendar(tasks_df, start_filter=None, end_filter=None):
    """Return a dataframe exploded into one row per resource per day within the window."""

    if tasks_df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in tasks_df.iterrows():
        start = row["Start"]
        end = row["Finish"]

        if start_filter:
            start = max(start, start_filter)
        if end_filter:
            end = min(end, end_filter)

        if start > end:
            continue

        for dt in pd.date_range(start, end, freq="D"):
            rows.append(
                {
                    "date": dt,
                    "resource_id": row["resource_id"],
                    "resource_name": row["resource_name"],
                    "resource_type": row["resource_type"],
                    "status": row["status"],
                    "title": row["title"],
                }
            )

    return pd.DataFrame(rows)


def ordered_resource_labels(res_df):
    """Return labels grouped vessels -> projects -> people for tidy timelines."""

    vessels = res_df[res_df["type"] == "Vessel"]["label"].tolist()
    projects = res_df[res_df["type"] == "Project"]["label"].tolist()
    people = res_df[res_df["type"] == "Person"]["label"].tolist()
    return vessels + projects + people


def compute_utilization(calendar_df, start_filter, end_filter):
    """Calculate busy days and utilization percentage per resource for a window."""

    if calendar_df.empty:
        return pd.DataFrame()

    total_days = (end_filter.normalize() - start_filter.normalize()).days + 1
    if total_days <= 0:
        return pd.DataFrame()

    utilization = (
        calendar_df.groupby(["resource_id", "resource_name", "resource_type"])
        ["date"]
        .nunique()
        .reset_index(name="busy_days")
    )
    utilization["available_days"] = total_days
    utilization["utilization"] = (utilization["busy_days"] / total_days * 100).round(1)
    return utilization.sort_values("utilization", ascending=False)


def safe_unique(df, column):
    """Safely return unique values even when duplicate column labels exist."""

    if column not in df.columns:
        return []
    col = df.loc[:, [column]]
    if isinstance(col, pd.DataFrame):
        col = col.iloc[:, 0]
    return sorted(pd.Series(col).dropna().unique().tolist())


def insert_resource(name, rtype, color):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO resources (name, type, color, active) VALUES (?, ?, ?, 1)",
        (name, rtype, color),
    )
    conn.commit()
    conn.close()


def update_resource(res_id, name, rtype, color, active):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE resources SET name = ?, type = ?, color = ?, active = ? WHERE id = ?",
        (name, rtype, color, 1 if active else 0, res_id),
    )
    conn.commit()
    conn.close()


def delete_resource(res_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE resource_id = ?", (res_id,))
    c.execute("DELETE FROM resources WHERE id = ?", (res_id,))
    conn.commit()
    conn.close()


def insert_task(resource_id, title, description, start_date, end_date, status):
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tasks
        (resource_id, title, description, start_date, end_date, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (resource_id, title, description, start_date.isoformat(),
          end_date.isoformat(), status, now, now))
    conn.commit()
    conn.close()


def update_task(task_id, resource_id, title, description, start_date, end_date, status):
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE tasks
        SET resource_id = ?, title = ?, description = ?, start_date = ?, end_date = ?, status = ?, updated_at = ?
        WHERE id = ?
    """, (resource_id, title, description, start_date.isoformat(),
          end_date.isoformat(), status, now, task_id))
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


# ---------- Session-state helpers ----------

def ensure_session_state():
    if "task_form_mode" not in st.session_state:
        st.session_state["task_form_mode"] = "create"
    if "edit_task_id" not in st.session_state:
        st.session_state["edit_task_id"] = None
    if "res_form_mode" not in st.session_state:
        st.session_state["res_form_mode"] = "create"
    if "edit_res_id" not in st.session_state:
        st.session_state["edit_res_id"] = None


def reset_task_form():
    st.session_state["task_form_mode"] = "create"
    st.session_state["edit_task_id"] = None


def reset_resource_form():
    st.session_state["res_form_mode"] = "create"
    st.session_state["edit_res_id"] = None


# ---------- Pages ----------

def page_schedule():
    st.header("Schedule")

    resources = fetch_resources(active_only=True)
    if not resources:
        st.info("No resources yet. Go to the **Resources** tab to add vessels, projects or people.")
        return

    res_df = pd.DataFrame(resources)
    res_df["label"] = res_df["type"] + " – " + res_df["name"]

    tasks_all = fetch_tasks()
    base_task_df = pd.DataFrame(tasks_all) if tasks_all else pd.DataFrame()
    if not base_task_df.empty:
        min_date = pd.to_datetime(base_task_df["start_date"]).min().date()
        max_date = pd.to_datetime(base_task_df["end_date"]).max().date()
    else:
        min_date = date.today()
        max_date = date.today()

    # Filters and zoom
    st.subheader("Filters & zoom")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        types = safe_unique(res_df, "type")
        selected_types = st.multiselect("Resource types", types, default=types)

    with col2:
        selected_res = st.multiselect(
            "Resources",
            options=res_df["label"],
            default=res_df["label"],
            help="Pick which vessels, projects or people to show",
        )

    with col3:
        status_filter = st.multiselect(
            "Task status",
            STATUS_OPTIONS,
            default=STATUS_OPTIONS,
        )

    with col4:
        zoom_choice = st.radio(
            "Zoom",
            options=["90 days", "6 months", "Full year", "Custom"],
            horizontal=True,
            index=1,
        )

    if zoom_choice == "Full year":
        start_filter, end_filter = pd.to_datetime(min_date), pd.to_datetime(max_date)
    elif zoom_choice == "90 days":
        end_filter = pd.to_datetime(max_date)
        start_filter = end_filter - pd.Timedelta(days=89)
    elif zoom_choice == "6 months":
        end_filter = pd.to_datetime(max_date)
        start_filter = end_filter - pd.Timedelta(days=182)
    else:
        date_range = st.date_input(
            "Custom window",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(date_range, tuple):
            start_filter, end_filter = [pd.to_datetime(d) for d in date_range]
        else:
            start_filter = end_filter = pd.to_datetime(date_range)

    start_filter = max(start_filter, pd.to_datetime(min_date))
    end_filter = min(end_filter, pd.to_datetime(max_date))

    # Filtered resources for task form
    st.subheader("Add / Edit Task")

    resources_filtered = res_df[
        (res_df["type"].isin(selected_types)) &
        (res_df["label"].isin(selected_res))
    ]

    if resources_filtered.empty:
        st.warning("No resources match the current filter. Adjust filters above.")
        return

    res_options = dict(zip(resources_filtered["label"], resources_filtered["id"]))

    # Decide if we are in create or edit mode
    mode = st.session_state["task_form_mode"]

    if mode == "edit" and st.session_state["edit_task_id"]:
        task_row = next((t for t in tasks_all if t["id"] == st.session_state["edit_task_id"]), None)
        if task_row:
            default_res_label = res_df[res_df["id"] == task_row["resource_id"]]["label"].iloc[0]
            default_title = task_row["title"]
            default_desc = task_row["description"] or ""
            default_start = date.fromisoformat(task_row["start_date"])
            default_end = date.fromisoformat(task_row["end_date"])
            default_status = task_row["status"]
        else:
            reset_task_form()
            default_res_label = list(res_options.keys())[0]
            default_title = ""
            default_desc = ""
            default_start = date.today()
            default_end = date.today()
            default_status = STATUS_OPTIONS[0]
    else:
        default_res_label = list(res_options.keys())[0]
        default_title = ""
        default_desc = ""
        default_start = date.today()
        default_end = date.today()
        default_status = STATUS_OPTIONS[0]

    col_a, col_b = st.columns(2)

    with col_a:
        res_label = st.selectbox(
            "Resource",
            list(res_options.keys()),
            index=list(res_options.keys()).index(default_res_label),
        )
        title = st.text_input("Task title", value=default_title)
        status = st.selectbox(
            "Status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(default_status) if default_status in STATUS_OPTIONS else 0,
        )

    with col_b:
        start_date = st.date_input("Start date", value=default_start)
        end_date = st.date_input("End date", value=default_end)
        description = st.text_area("Description", value=default_desc, height=80)

    col_buttons = st.columns(3)
    with col_buttons[0]:
        if mode == "create":
            if st.button("➕ Create task"):
                if title.strip():
                    insert_task(
                        resource_id=res_options[res_label],
                        title=title.strip(),
                        description=description.strip(),
                        start_date=start_date,
                        end_date=end_date,
                        status=status,
                    )
                    st.success("Task created.")
                    reset_task_form()
                    st.experimental_rerun()
                else:
                    st.error("Task title is required.")
        else:
            if st.button("💾 Save changes"):
                if title.strip():
                    update_task(
                        task_id=st.session_state["edit_task_id"],
                        resource_id=res_options[res_label],
                        title=title.strip(),
                        description=description.strip(),
                        start_date=start_date,
                        end_date=end_date,
                        status=status,
                    )
                    st.success("Task updated.")
                    reset_task_form()
                    st.experimental_rerun()
                else:
                    st.error("Task title is required.")

    with col_buttons[1]:
        if mode == "edit":
            if st.button("❌ Cancel edit"):
                reset_task_form()
                st.experimental_rerun()

    with col_buttons[2]:
        if mode == "edit" and st.session_state["edit_task_id"]:
            if st.button("🗑 Delete task"):
                delete_task(st.session_state["edit_task_id"])
                st.success("Task deleted.")
                reset_task_form()
                st.experimental_rerun()

    if not tasks_all:
        st.info("No tasks yet. Add one above.")
        return

    tasks_df = pd.DataFrame(tasks_all)
    tasks_df = tasks_df.merge(
        res_df[["id", "label", "type"]],
        left_on="resource_id",
        right_on="id",
        how="left",
        suffixes=("", "_res"),
    )
    tasks_df.rename(columns={"label": "ResourceLabel", "type": "ResourceType"}, inplace=True)
    tasks_df["Start"] = pd.to_datetime(tasks_df["start_date"])
    tasks_df["Finish"] = pd.to_datetime(tasks_df["end_date"])
    tasks_df["TaskLabel"] = (
        tasks_df.apply(lambda r: f"{r['title']} — {r['description'] or ''}".strip(" —"), axis=1)
        .str.slice(0, 55)
    )

    tasks_df = tasks_df[
        (tasks_df["ResourceType"].isin(selected_types))
        & (tasks_df["ResourceLabel"].isin(selected_res))
        & (tasks_df["status"].isin(status_filter))
        & (tasks_df["Start"] <= end_filter)
        & (tasks_df["Finish"] >= start_filter)
    ]

    if tasks_df.empty:
        st.warning("No tasks match the current filters.")
        return

    # Timeline chart
    st.subheader("Timeline")

    ordered_labels = [lbl for lbl in ordered_resource_labels(res_df) if lbl in tasks_df["ResourceLabel"].unique()]
    fig = px.timeline(
        tasks_df,
        x_start="Start",
        x_end="Finish",
        y="ResourceLabel",
        color="status",
        text="TaskLabel",
        custom_data=["title", "description", "start_date", "end_date", "status", "ResourceLabel"],
        color_discrete_map=STATUS_COLORS,
    )
    fig.update_traces(
        textposition="inside",
        insidetextanchor="middle",
        marker_line_color="#E0E7F1",
        marker_line_width=1.2,
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Start: %{customdata[2]}<br>End: %{customdata[3]}<br>Status: %{customdata[4]}<br>Resource: %{customdata[5]}",
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=True,
        gridcolor="#DCE4F2",
        categoryorder="array",
        categoryarray=ordered_labels,
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#DCE4F2",
        dtick="M1",
        tickformat="%b %d",
        rangeslider_visible=True,
        range=[start_filter, end_filter],
    )
    fig.update_layout(
        height=520,
        bargap=0.25,
        plot_bgcolor=PALETTE["background"],
        paper_bgcolor=PALETTE["background"],
        legend_title_text="Status",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Utilization and load summaries
    st.subheader("Load snapshot")
    calendar_df = expand_tasks_to_calendar(tasks_df, start_filter, end_filter)
    util_df = compute_utilization(calendar_df, start_filter, end_filter)

    col_util, col_heat = st.columns((1, 1))
    with col_util:
        if util_df.empty:
            st.info("No workload in this window.")
        else:
            util_df_display = util_df.rename(
                columns={
                    "resource_name": "Resource",
                    "resource_type": "Type",
                    "busy_days": "Busy days",
                    "available_days": "Days in window",
                    "utilization": "Utilisation %",
                }
            )
            st.dataframe(util_df_display, use_container_width=True)

    with col_heat:
        if not calendar_df.empty:
            calendar_df["date_only"] = calendar_df["date"].dt.date
            pivot = calendar_df.pivot_table(
                index="resource_name",
                columns="date_only",
                values="title",
                aggfunc="count",
                fill_value=0,
            )
            fig_heat = px.imshow(
                pivot,
                aspect="auto",
                labels={"x": "Date", "y": "Resource", "color": "# tasks"},
                color_continuous_scale="Blues",
            )
            fig_heat.update_layout(height=350, plot_bgcolor=PALETTE["background"], paper_bgcolor=PALETTE["background"])
            st.plotly_chart(fig_heat, use_container_width=True)

    st.subheader("Task list")
    display_cols = [
        "id",
        "ResourceLabel",
        "title",
        "description",
        "status",
        "start_date",
        "end_date",
    ]
    st.dataframe(
        tasks_df[display_cols].rename(columns={
            "id": "Task ID",
            "ResourceLabel": "Resource",
            "title": "Title",
            "status": "Status",
            "start_date": "Start",
            "end_date": "End",
        }),
        use_container_width=True,
    )

    # Select task to edit
    edit_id = st.selectbox(
        "Select task to edit",
        options=["(none)"] + [str(i) for i in tasks_df["id"].tolist()],
        index=0,
    )
    if edit_id != "(none)":
        st.session_state["task_form_mode"] = "edit"
        st.session_state["edit_task_id"] = int(edit_id)
        st.experimental_rerun()


def page_dashboard():
    st.header("Resource planning dashboard")

    tasks_df = load_tasks_with_resources()
    if tasks_df.empty:
        st.info("Add resources and tasks to see dashboard insights.")
        return

    min_date = tasks_df["Start"].min().date()
    max_date = tasks_df["Finish"].max().date()

    st.subheader("Filters")
    c1, c2, c3 = st.columns(3)

    with c1:
        date_range = st.date_input(
            "Date window",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    with c2:
        type_filter = st.multiselect(
            "Resource types",
            options=safe_unique(tasks_df, "resource_type"),
            default=safe_unique(tasks_df, "resource_type"),
        )

    with c3:
        status_filter = st.multiselect(
            "Statuses",
            options=list(STATUS_COLORS.keys()),
            default=list(STATUS_COLORS.keys()),
        )

    if isinstance(date_range, tuple):
        start_filter, end_filter = [pd.to_datetime(d) for d in date_range]
    else:
        start_filter = end_filter = pd.to_datetime(date_range)

    tasks_df = tasks_df[
        tasks_df["resource_type"].isin(type_filter)
        & tasks_df["status"].isin(status_filter)
    ]

    tasks_df = tasks_df[
        (tasks_df["Start"] <= end_filter) & (tasks_df["Finish"] >= start_filter)
    ]

    if tasks_df.empty:
        st.warning("No tasks in this filter. Try expanding the date range or filters above.")
        return

    calendar_df = expand_tasks_to_calendar(tasks_df, start_filter=start_filter, end_filter=end_filter)
    util_df = compute_utilization(calendar_df, start_filter, end_filter)
    avg_utilisation = round(util_df["utilization"].mean(), 1) if not util_df.empty else 0

    # KPI cards
    total_tasks = len(tasks_df)
    active_resources = calendar_df["resource_name"].nunique()
    busiest = (
        calendar_df.groupby("resource_name")["date"]
        .nunique()
        .reset_index()
        .rename(columns={"date": "busy_days"})
        .sort_values("busy_days", ascending=False)
    )
    most_busy_label = busiest.iloc[0]

    st.subheader("Highlights")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(
            f"""
            <div class='metric-card'>
                <div style='color:{PALETTE['primary']};text-transform:uppercase;font-size:12px;font-weight:700;'>Tasks</div>
                <div style='font-size:32px;font-weight:800;'>{total_tasks}</div>
                <div style='color:#4B5563;'>Scheduled in window</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi2:
        st.markdown(
            f"""
            <div class='metric-card'>
                <div style='color:{PALETTE['primary']};text-transform:uppercase;font-size:12px;font-weight:700;'>Resources</div>
                <div style='font-size:32px;font-weight:800;'>{active_resources}</div>
                <div style='color:#4B5563;'>Active in this period</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi3:
        st.markdown(
            f"""
            <div class='metric-card'>
                <div style='color:{PALETTE['primary']};text-transform:uppercase;font-size:12px;font-weight:700;'>Busiest</div>
                <div style='font-size:24px;font-weight:800;'>{most_busy_label['resource_name']}</div>
                <div style='color:#4B5563;'>{most_busy_label['busy_days']} busy days</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi4:
        st.markdown(
            f"""
            <div class='metric-card'>
                <div style='color:{PALETTE['primary']};text-transform:uppercase;font-size:12px;font-weight:700;'>Avg utilisation</div>
                <div style='font-size:32px;font-weight:800;'>{avg_utilisation}%</div>
                <div style='color:#4B5563;'>Across filtered window</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    col_a, col_b = st.columns((2, 1))

    with col_a:
        st.subheader("Heat map: busy resources by week")
        calendar_df["week"] = calendar_df["date"].dt.to_period("W").apply(lambda r: r.start_time.date())
        heat_df = (
            calendar_df.groupby(["resource_name", "week"])["date"]
            .nunique()
            .reset_index(name="busy_days")
        )

        heat_df["week_label"] = heat_df["week"].astype(str)

        fig = px.density_heatmap(
            heat_df,
            x="week_label",
            y="resource_name",
            z="busy_days",
            color_continuous_scale="Blues",
            labels={"week_label": "Week starting", "resource_name": "Resource", "busy_days": "Busy days"},
        )
        fig.update_layout(
            height=450,
            plot_bgcolor=PALETTE["background"],
            paper_bgcolor=PALETTE["background"],
            xaxis_title="Week",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Status mix")
        status_summary = (
            tasks_df.groupby("status")["id"].count().reset_index(name="count")
        )
        fig_status = px.pie(
            status_summary,
            names="status",
            values="count",
            color="status",
            color_discrete_map=STATUS_COLORS,
            hole=0.45,
        )
        fig_status.update_layout(plot_bgcolor=PALETTE["background"], paper_bgcolor=PALETTE["background"])
        st.plotly_chart(fig_status, use_container_width=True)

    st.markdown("---")

    load_col, leave_col = st.columns((1, 1))

    with load_col:
        st.subheader("Workload by type")
        workload_type = (
            calendar_df.groupby("resource_type")["date"].nunique().reset_index(name="busy_days")
        )
        fig_type = px.bar(
            workload_type,
            x="resource_type",
            y="busy_days",
            color="resource_type",
            color_discrete_sequence=[PALETTE["primary"], PALETTE["accent"], PALETTE["muted"]],
            labels={"resource_type": "Type", "busy_days": "Busy days"},
        )
        fig_type.update_layout(plot_bgcolor=PALETTE["background"], paper_bgcolor=PALETTE["background"], showlegend=False)
        st.plotly_chart(fig_type, use_container_width=True)

    with leave_col:
        st.subheader("Time off & holiday")
        leave_df = tasks_df[tasks_df["status"].isin(["Holiday", "Time Off"])]
        if leave_df.empty:
            st.caption("No time off scheduled in this window.")
        else:
            st.dataframe(
                leave_df[["resource_name", "title", "start_date", "end_date", "status"]]
                .rename(
                    columns={
                        "resource_name": "Resource",
                        "title": "Reason",
                        "start_date": "Start",
                        "end_date": "End",
                        "status": "Type",
                    }
                ),
                use_container_width=True,
            )

    st.markdown("---")

    col_c, col_d, col_e = st.columns((1, 1, 1))

    with col_c:
        st.subheader("Top busy resources")
        st.dataframe(
            busiest.rename(columns={"resource_name": "Resource", "busy_days": "Busy days"}),
            use_container_width=True,
        )

    with col_d:
        st.subheader("Upcoming tasks")
        upcoming = tasks_df.sort_values("Start").head(10)
        st.dataframe(
            upcoming[["resource_name", "title", "status", "start_date", "end_date"]]
            .rename(
                columns={
                    "resource_name": "Resource",
                    "title": "Task",
                    "status": "Status",
                    "start_date": "Start",
                    "end_date": "End",
                }
            ),
            use_container_width=True,
        )

    with col_e:
        st.subheader("Watchlist (≥80% utilised)")
        watchlist = util_df[util_df["utilization"] >= 80]
        if watchlist.empty:
            st.caption("No utilisation risks in this window.")
        else:
            st.dataframe(
                watchlist[["resource_name", "resource_type", "busy_days", "utilization"]]
                .rename(
                    columns={
                        "resource_name": "Resource",
                        "resource_type": "Type",
                        "busy_days": "Busy days",
                        "utilization": "Utilisation %",
                    }
                ),
                use_container_width=True,
            )


def page_resources():
    st.header("Resources (Vessels / Projects / People)")

    resources = fetch_resources(active_only=False)
    if resources:
        df = pd.DataFrame(resources)
        df_display = df[["id", "name", "type", "color", "active"]].rename(columns={
            "id": "ID",
            "name": "Name",
            "type": "Type",
            "color": "Color",
            "active": "Active",
        })
        st.subheader("Existing resources")
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("No resources yet. Add one below.")

    st.subheader("Add / Edit resource")

    mode = st.session_state["res_form_mode"]

    if mode == "edit" and st.session_state["edit_res_id"]:
        res_all = fetch_resources(active_only=False)
        row = next((r for r in res_all if r["id"] == st.session_state["edit_res_id"]), None)
        if row:
            default_name = row["name"]
            default_type = row["type"]
            default_color = row["color"] or ""
            default_active = bool(row["active"])
        else:
            reset_resource_form()
            default_name = ""
            default_type = "Person"
            default_color = ""
            default_active = True
    else:
        default_name = ""
        default_type = "Person"
        default_color = ""
        default_active = True

    col1, col2, col3 = st.columns(3)

    with col1:
        name = st.text_input("Name", value=default_name)

    with col2:
        rtype = st.selectbox(
            "Type",
            ["Vessel", "Project", "Person"],
            index=["Vessel", "Project", "Person"].index(default_type),
        )

    with col3:
        color = st.text_input(
            "Color (optional, e.g. 'blue' or '#357ba2')",
            value=default_color,
        )

    active = st.checkbox("Active", value=default_active)

    col_btns = st.columns(3)
    with col_btns[0]:
        if mode == "create":
            if st.button("➕ Create resource"):
                if name.strip():
                    insert_resource(name.strip(), rtype, color.strip() or None)
                    st.success("Resource created.")
                    reset_resource_form()
                    st.experimental_rerun()
                else:
                    st.error("Name is required.")
        else:
            if st.button("💾 Save resource"):
                if name.strip():
                    update_resource(
                        res_id=st.session_state["edit_res_id"],
                        name=name.strip(),
                        rtype=rtype,
                        color=color.strip() or None,
                        active=active,
                    )
                    st.success("Resource updated.")
                    reset_resource_form()
                    st.experimental_rerun()
                else:
                    st.error("Name is required.")

    with col_btns[1]:
        if mode == "edit":
            if st.button("❌ Cancel edit"):
                reset_resource_form()
                st.experimental_rerun()

    with col_btns[2]:
        if mode == "edit" and st.session_state["edit_res_id"]:
            if st.button("🗑 Delete resource (and its tasks)"):
                delete_resource(st.session_state["edit_res_id"])
                st.success("Resource and its tasks deleted.")
                reset_resource_form()
                st.experimental_rerun()

    st.subheader("Select resource to edit")
    resources = fetch_resources(active_only=False)
    if resources:
        options = ["(none)"] + [f"{r['id']} – {r['type']} – {r['name']}" for r in resources]
        selection = st.selectbox("Resource", options, index=0)
        if selection != "(none)":
            res_id = int(selection.split("–")[0].strip())
            st.session_state["res_form_mode"] = "edit"
            st.session_state["edit_res_id"] = res_id
            st.experimental_rerun()


def page_tasks_raw():
    st.header("All tasks (raw table)")

    tasks = fetch_tasks()
    if not tasks:
        st.info("No tasks yet.")
        return

    df = pd.DataFrame(tasks)
    df_display = df[[
        "id", "resource_name", "title", "status",
        "start_date", "end_date", "created_at", "updated_at"
    ]].rename(columns={
        "id": "ID",
        "resource_name": "Resource",
        "title": "Title",
        "status": "Status",
        "start_date": "Start",
        "end_date": "End",
        "created_at": "Created",
        "updated_at": "Updated",
    })
    st.dataframe(df_display, use_container_width=True)


# ---------- Main ----------

def main():
    st.set_page_config(page_title="Resource Scheduler", layout="wide", page_icon="📅")
    inject_styles()
    ensure_session_state()
    init_db()
    seed_demo_data()

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "Schedule", "Resources", "All tasks"])

    st.sidebar.markdown("---")
    st.sidebar.caption("Resource planning toolkit")

    if page == "Dashboard":
        page_dashboard()
    elif page == "Schedule":
        page_schedule()
    elif page == "Resources":
        page_resources()
    elif page == "All tasks":
        page_tasks_raw()


if __name__ == "__main__":
    main()
