import io
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from auth import (
    get_authenticated_username,
    is_auth_enabled,
    logout,
    require_authentication,
)
from database import (
    create_session,
    get_all_leads,
    get_all_sessions,
    get_database_path,
    get_session_leads,
    init_db,
    save_leads,
    update_tag,
)
from extractor import extract_lead
from scoring import (
    analyze_digital_presence,
    compute_lead_quality_score,
)
from search import run_search
from utils import clean_name, deduplicate_leads, logger

load_dotenv()

st.set_page_config(
    page_title="Lead Research Dashboard",
    page_icon="L",
    layout="wide",
    initial_sidebar_state="expanded",
)

for key, value in [("session_id", None), ("search_done", False)]:
    if key not in st.session_state:
        st.session_state[key] = value

require_authentication()
init_db()

TAG_OPTIONS = ["Untagged", "Hot", "Warm", "Skip"]
SHOW_COLS = [
    "name",
    "sector",
    "city",
    "instagram_url",
    "website",
    "phone",
    "email",
    "bio",
    "digital_presence_score",
    "digital_presence_notes",
    "lead_quality_score",
    "tag",
    "source_url",
]


with st.sidebar:
    st.title("Lead Research")
    st.caption("Ethical B2B prospecting using public data")
    if is_auth_enabled():
        st.caption(f"Signed in as `{get_authenticated_username()}`")
        st.button("Log out", use_container_width=True, on_click=logout)
    st.divider()

    city = st.text_input("City", placeholder="e.g. Bangalore")
    sector = st.text_input(
        "Sector",
        placeholder="e.g. wedding photographers",
        help="Be specific: 'bridal makeup artists Bangalore' beats 'makeup'.",
    )

    st.subheader("Filters")
    must_instagram = st.checkbox("Must have Instagram")
    must_phone = st.checkbox("Must have Phone / WhatsApp")
    weak_only = st.checkbox("Weak digital presence only (DP score >= 5)")
    max_results = st.slider("Max results", 10, 100, 30, step=5)

    st.divider()
    search_btn = st.button(
        "Start Search",
        use_container_width=True,
        type="primary",
        disabled=not (city.strip() and sector.strip()),
    )

    using_paid = bool(
        os.getenv("SERPAPI_KEY")
        or (os.getenv("GOOGLE_CSE_KEY") and os.getenv("GOOGLE_CSE_ID"))
    )
    if using_paid:
        st.success("Paid search API active")
    else:
        st.info("Using DuckDuckGo free search")

    st.divider()
    st.subheader("Past Sessions")
    sessions = get_all_sessions()
    session_map: dict[str, int] = {
        f"{s['sector']} / {s['city']} - {s['created_at'][:10]} ({s['result_count']} leads)": s["id"]
        for s in sessions
    }
    selected_label = st.selectbox(
        "Load session",
        ["New search"] + list(session_map.keys()),
    )
    st.caption(f"Database: `{get_database_path()}`")


def _apply_filters(leads: list) -> list:
    filtered = leads
    if must_instagram:
        filtered = [lead for lead in filtered if lead.get("instagram_url")]
    if must_phone:
        filtered = [lead for lead in filtered if lead.get("phone")]
    if weak_only:
        filtered = [
            lead
            for lead in filtered
            if (lead.get("digital_presence_score") or 0) >= 5
        ]
    return filtered


def display_leads(leads: list, session_id: int, export_label: str = "leads"):
    filtered = _apply_filters(leads)
    if not filtered:
        st.warning("No leads match the current filters.")
        return

    df = pd.DataFrame(filtered)
    visible_columns = [column for column in SHOW_COLS if column in df.columns]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total leads", len(df))
    c2.metric(
        "With Instagram",
        int(df["instagram_url"].astype(str).str.len().gt(0).sum()),
    )
    c3.metric("With phone", int(df["phone"].astype(str).str.len().gt(0).sum()))
    c4.metric("Avg quality", f"{df['lead_quality_score'].mean():.1f} / 10")
    st.divider()

    if "tag" in df.columns:
        tag_counts = df["tag"].value_counts().to_dict()
        st.caption(
            " | ".join(f"**{tag}** {tag_counts.get(tag, 0)}" for tag in TAG_OPTIONS)
        )

    lead_ids = df["id"].tolist() if "id" in df.columns else []
    original_tags = df["tag"].tolist() if "tag" in df.columns else []

    edited = st.data_editor(
        df[visible_columns].reset_index(drop=True),
        column_config={
            "tag": st.column_config.SelectboxColumn(
                "Tag", options=TAG_OPTIONS, required=True
            ),
            "instagram_url": st.column_config.LinkColumn(
                "Instagram",
                display_text=r"instagram\.com/([^/?]+)",
            ),
            "website": st.column_config.LinkColumn("Website"),
            "source_url": st.column_config.LinkColumn("Source"),
            "digital_presence_score": st.column_config.NumberColumn(
                "DP Score",
                help="Higher means a weaker digital presence and a stronger outreach angle.",
                min_value=0,
                max_value=10,
            ),
            "digital_presence_notes": st.column_config.TextColumn(
                "DP Notes",
                help="Short explanation of the digital presence score.",
                width="large",
            ),
            "lead_quality_score": st.column_config.NumberColumn(
                "Quality", format="%.1f", min_value=0.0, max_value=10.0
            ),
            "bio": st.column_config.TextColumn("Bio", width="large"),
            "name": st.column_config.TextColumn("Name", width="medium"),
        },
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key=f"table_{session_id}",
    )

    if edited is not None and lead_ids and "tag" in edited.columns:
        for index, new_tag in enumerate(edited["tag"].tolist()):
            if index < len(lead_ids) and index < len(original_tags):
                if new_tag and new_tag != original_tags[index]:
                    update_tag(lead_ids[index], new_tag)

    st.divider()
    buffer = io.StringIO()
    df[visible_columns].to_csv(buffer, index=False)
    st.download_button(
        "Export CSV",
        data=buffer.getvalue(),
        file_name=f"{export_label}.csv",
        mime="text/csv",
    )


def run_full_search(sector: str, city: str, max_results: int) -> int:
    search_prog = st.progress(0, text="Starting search...")

    def on_search_progress(progress: float, message: str):
        search_prog.progress(min(progress, 1.0), text=message)

    raw_results = run_search(
        sector, city, max_results=max_results, progress_callback=on_search_progress
    )

    if not raw_results:
        st.warning(
            "No results returned. DuckDuckGo may be rate-limiting. Wait a minute and try again."
        )
        return 0

    session_id = create_session(sector, city)

    leads: list[dict] = []
    extract_prog = st.progress(0, text="Extracting lead info...")
    total = len(raw_results)

    for index, result in enumerate(raw_results, start=1):
        extract_prog.progress(
            index / total,
            text=f"Extracting {index}/{total}: {result.get('url', '')[:70]}",
        )
        try:
            lead = extract_lead(result, sector, city)
            lead["name"] = clean_name(lead.get("name", ""))
            presence = analyze_digital_presence(lead)
            lead["digital_presence_score"] = presence["score"]
            lead["digital_presence_notes"] = presence["notes"]
            lead["lead_quality_score"] = compute_lead_quality_score(lead)
            leads.append(lead)
        except Exception as exc:
            logger.error(f"Extract error {result.get('url')}: {exc}")

    leads = deduplicate_leads(leads)
    saved = save_leads(leads, session_id)
    st.success(f"Saved **{saved}** unique leads.")
    return session_id


st.title("B2B Lead Research Dashboard")
st.caption(
    "Find publicly listed business and social profiles via web search. "
    "Only public data is used."
)

if search_btn:
    if not city.strip() or not sector.strip():
        st.error("Please enter both **City** and **Sector**.")
    else:
        with st.spinner("Running search pipeline..."):
            session_id = run_full_search(sector.strip(), city.strip(), max_results)
        if session_id:
            st.session_state.session_id = session_id
            st.session_state.search_done = True
            st.rerun()

elif st.session_state.search_done and st.session_state.session_id:
    session_id = st.session_state.session_id
    leads = get_session_leads(session_id)
    st.subheader(f"Results - {len(leads)} leads found")
    display_leads(leads, session_id, export_label=f"leads_session_{session_id}")

elif selected_label != "New search":
    session_id = session_map[selected_label]
    leads = get_session_leads(session_id)
    st.subheader(f"Session: {selected_label}")
    display_leads(leads, session_id, export_label=f"leads_session_{session_id}")

else:
    st.info(
        "Enter a **city** and **sector** in the sidebar, then click **Start Search**.\n\n"
        "Results are saved and can be reloaded from **Past Sessions**."
    )
    all_leads = get_all_leads()
    if all_leads:
        st.divider()
        df_all = pd.DataFrame(all_leads)
        st.subheader(f"All Stored Leads ({len(all_leads)})")
        st.dataframe(
            df_all[[column for column in SHOW_COLS if column in df_all.columns]],
            use_container_width=True,
            hide_index=True,
        )
