import io
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from database import (
    create_session,
    get_all_leads,
    get_all_sessions,
    get_session_leads,
    init_db,
    save_leads,
    update_tag,
)
from extractor import extract_lead
from scoring import compute_digital_presence_score, compute_lead_quality_score
from search import run_search
from utils import clean_name, deduplicate_leads, logger

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Lead Research Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

for _k, _v in [("session_id", None), ("search_done", False)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

TAG_OPTIONS = ["Untagged", "Hot", "Warm", "Skip"]

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🔍 Lead Research")
    st.caption("Ethical B2B prospecting · 100% free")
    st.divider()

    city = st.text_input("City", placeholder="e.g. Bangalore")
    sector = st.text_input(
        "Sector",
        placeholder="e.g. wedding photographers",
        help="Be specific — 'bridal makeup artists Bangalore' beats 'makeup'",
    )

    st.subheader("Filters")
    must_instagram = st.checkbox("Must have Instagram")
    must_phone = st.checkbox("Must have Phone / WhatsApp")
    weak_only = st.checkbox("Weak digital presence only  (DP score ≥ 5)")
    max_results = st.slider("Max results", 10, 100, 30, step=5)

    st.divider()
    search_btn = st.button(
        "🚀 Start Search",
        use_container_width=True,
        type="primary",
        disabled=not (city.strip() and sector.strip()),
    )

    # Optional API upgrade notice
    using_paid = bool(
        os.getenv("SERPAPI_KEY")
        or (os.getenv("GOOGLE_CSE_KEY") and os.getenv("GOOGLE_CSE_ID"))
    )
    if using_paid:
        st.success("✅ Paid search API active")
    else:
        st.info("🦆 Using DuckDuckGo (free, no key needed)")

    st.divider()
    st.subheader("Past Sessions")
    sessions = get_all_sessions()
    session_map: dict[str, int] = {
        f"{s['sector']} / {s['city']}  ·  {s['created_at'][:10]}  ({s['result_count']} leads)": s["id"]
        for s in sessions
    }
    selected_label = st.selectbox(
        "Load session",
        ["— New search —"] + list(session_map.keys()),
    )

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _apply_filters(leads: list) -> list:
    out = leads
    if must_instagram:
        out = [l for l in out if l.get("instagram_url")]
    if must_phone:
        out = [l for l in out if l.get("phone")]
    if weak_only:
        out = [l for l in out if (l.get("digital_presence_score") or 0) >= 5]
    return out


SHOW_COLS = [
    "name", "sector", "city",
    "instagram_url", "website",
    "phone", "email", "bio",
    "digital_presence_score", "lead_quality_score",
    "tag", "source_url",
]


def display_leads(leads: list, session_id: int, export_label: str = "leads"):
    filtered = _apply_filters(leads)
    if not filtered:
        st.warning("No leads match the current filters.")
        return

    df = pd.DataFrame(filtered)
    show = [c for c in SHOW_COLS if c in df.columns]

    # ── Metrics ────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total leads", len(df))
    c2.metric(
        "With Instagram",
        int(df["instagram_url"].astype(str).str.len().gt(0).sum()),
    )
    c3.metric("With phone", int(df["phone"].astype(str).str.len().gt(0).sum()))
    c4.metric("Avg quality", f"{df['lead_quality_score'].mean():.1f} / 10")
    st.divider()

    # ── Tag summary ────────────────────────────────────────────────────────
    if "tag" in df.columns:
        tag_counts = df["tag"].value_counts().to_dict()
        st.caption(
            "  |  ".join(
                f"**{t}** {tag_counts.get(t, 0)}" for t in TAG_OPTIONS
            )
        )

    # ── IDs for tag persistence ────────────────────────────────────────────
    lead_ids = df["id"].tolist() if "id" in df.columns else []
    original_tags = df["tag"].tolist() if "tag" in df.columns else []

    # ── Editable table ────────────────────────────────────────────────────
    edited = st.data_editor(
        df[show].reset_index(drop=True),
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
                help="Higher = weaker digital presence → better outreach target",
                min_value=0,
                max_value=10,
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

    # Auto-save tag edits to SQLite
    if edited is not None and lead_ids and "tag" in edited.columns:
        for i, new_tag in enumerate(edited["tag"].tolist()):
            if i < len(lead_ids) and i < len(original_tags):
                if new_tag and new_tag != original_tags[i]:
                    update_tag(lead_ids[i], new_tag)

    # ── CSV export ─────────────────────────────────────────────────────────
    st.divider()
    buf = io.StringIO()
    df[show].to_csv(buf, index=False)
    st.download_button(
        "⬇️ Export CSV",
        data=buf.getvalue(),
        file_name=f"{export_label}.csv",
        mime="text/csv",
    )


# ─── Search pipeline ─────────────────────────────────────────────────────────

def run_full_search(sector: str, city: str, max_results: int) -> int:
    session_id = create_session(sector, city)

    search_prog = st.progress(0, text="Starting search…")

    def on_search_progress(pct: float, msg: str):
        search_prog.progress(min(pct, 1.0), text=msg)

    raw = run_search(
        sector, city, max_results=max_results, progress_callback=on_search_progress
    )

    if not raw:
        st.warning(
            "No results returned. DuckDuckGo may be rate-limiting — wait a minute and try again."
        )
        return session_id

    leads: list[dict] = []
    xprog = st.progress(0, text="Extracting lead info…")
    total = len(raw)

    for i, result in enumerate(raw):
        xprog.progress(
            (i + 1) / total,
            text=f"Extracting {i+1}/{total}: {result.get('url', '')[:70]}",
        )
        try:
            lead = extract_lead(result, sector, city)
            lead["name"] = clean_name(lead.get("name", ""))
            lead["digital_presence_score"] = compute_digital_presence_score(lead)
            lead["lead_quality_score"] = compute_lead_quality_score(lead)
            leads.append(lead)
        except Exception as e:
            logger.error(f"Extract error {result.get('url')}: {e}")

    leads = deduplicate_leads(leads)
    saved = save_leads(leads, session_id)
    st.success(f"Saved **{saved}** unique leads.")
    return session_id


# ─── Main layout ─────────────────────────────────────────────────────────────

st.title("B2B Lead Research Dashboard")
st.caption(
    "Finds publicly listed business/social profiles via web search. "
    "Only public data — no private scraping."
)

if search_btn:
    if not city.strip() or not sector.strip():
        st.error("Please enter both **City** and **Sector**.")
    else:
        with st.spinner("Running search pipeline…"):
            sid = run_full_search(sector.strip(), city.strip(), max_results)
        st.session_state.session_id = sid
        st.session_state.search_done = True
        st.rerun()

elif st.session_state.search_done and st.session_state.session_id:
    sid = st.session_state.session_id
    leads = get_session_leads(sid)
    st.subheader(f"Results — {len(leads)} leads found")
    display_leads(leads, sid, export_label=f"leads_{sector}_{city}")

elif selected_label != "— New search —":
    sid = session_map[selected_label]
    leads = get_session_leads(sid)
    st.subheader(f"Session: {selected_label}")
    display_leads(leads, sid, export_label=f"leads_session_{sid}")

else:
    st.info(
        "Enter a **city** and **sector** in the sidebar, then click **Start Search**.\n\n"
        "Results are saved in a local SQLite database and reloadable from **Past Sessions**."
    )
    all_leads = get_all_leads()
    if all_leads:
        st.divider()
        df_all = pd.DataFrame(all_leads)
        st.subheader(f"All Stored Leads ({len(all_leads)})")
        st.dataframe(
            df_all[[c for c in SHOW_COLS if c in df_all.columns]],
            use_container_width=True,
            hide_index=True,
        )
