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
}


def inject_styles():
    """Apply a modern layout and brand colors."""

    st.markdown(
        f"""
        <style>
        .main > div {{
            background: linear-gradient(180deg, {PALETTE['background']} 0%, #F5F7FB 35%, #E9F2FF 100%);
            color: #1B263B;
        }}
        .sidebar .sidebar-content {{
            background: {PALETTE['primary']};
        }}
        .stButton button {{
            background: {PALETTE['primary']};
            color: {PALETTE['background']};
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: 600;
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
    resources = pd.DataFrame(fetch_resources(active_only=False))
    if resources.empty:
        return pd.DataFrame()

    tasks_df = tasks_df.merge(
        resources[["id", "name", "type", "color"]],
        left_on="resource_id",
        right_on="id",
        how="left",
        suffixes=("", "_res"),
    )
    tasks_df.rename(
        columns={
            "name": "resource_name",
            "type": "resource_type",
            "color": "resource_color",
        },
        inplace=True,
    )
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

    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)

    with col1:
        types = sorted(res_df["type"].unique().tolist())
        selected_types = st.multiselect("Resource types", types, default=types)

    with col2:
        selected_res = st.multiselect(
            "Resources",
            options=res_df["label"],
            default=res_df["label"],
        )

    with col3:
        status_filter = st.multiselect(
            "Task status",
            ["Planned", "In Progress", "Done", "On Hold", "Holiday"],
            default=["Planned", "In Progress", "Done", "On Hold", "Holiday"],
        )

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
        tasks_all = fetch_tasks()
        task_row = next((t for t in tasks_all if t["id"] == st.session_state["edit_task_id"]), None)
        if task_row:
            # Find label for current resource
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
            default_status = "Planned"
    else:
        default_res_label = list(res_options.keys())[0]
        default_title = ""
        default_desc = ""
        default_start = date.today()
        default_end = date.today()
        default_status = "Planned"

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
            ["Planned", "In Progress", "Done", "On Hold", "Holiday"],
            index=["Planned", "In Progress", "Done", "On Hold", "Holiday"].index(default_status),
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

    # Load tasks for chart + table
    tasks = fetch_tasks()
    if not tasks:
        st.info("No tasks yet. Add one above.")
        return

    tasks_df = pd.DataFrame(tasks)

    # Join resource label & type
    tasks_df = tasks_df.merge(
        res_df[["id", "label", "type"]],
        left_on="resource_id",
        right_on="id",
        how="left",
        suffixes=("", "_res"),
    )
    tasks_df.rename(columns={"label": "ResourceLabel", "type": "ResourceType"}, inplace=True)

    # Apply filters
    tasks_df = tasks_df[
        tasks_df["ResourceType"].isin(selected_types) &
        tasks_df["ResourceLabel"].isin(selected_res) &
        tasks_df["status"].isin(status_filter)
    ]

    if tasks_df.empty:
        st.warning("No tasks match the current filters.")
        return

    tasks_df["Start"] = pd.to_datetime(tasks_df["start_date"])
    tasks_df["Finish"] = pd.to_datetime(tasks_df["end_date"])

    # Timeline chart
    st.subheader("Timeline")
    fig = px.timeline(
        tasks_df,
        x_start="Start",
        x_end="Finish",
        y="ResourceLabel",
        color="status",
        hover_data=["title", "description"],
        color_discrete_map=STATUS_COLORS,
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(plot_bgcolor=PALETTE["background"], paper_bgcolor=PALETTE["background"])
    st.plotly_chart(fig, use_container_width=True)

    # Task table
    st.subheader("Task list")
    display_cols = ["id", "ResourceLabel", "title", "status", "start_date", "end_date"]
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
            options=sorted(tasks_df["resource_type"].dropna().unique().tolist()),
            default=sorted(tasks_df["resource_type"].dropna().unique().tolist()),
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

    if tasks_df.empty:
        st.warning("No tasks in this filter. Try expanding the date range or filters above.")
        return

    calendar_df = expand_tasks_to_calendar(tasks_df, start_filter=start_filter, end_filter=end_filter)

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
    kpi1, kpi2, kpi3 = st.columns(3)
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

    col_c, col_d = st.columns((1, 1))

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
