"""Blue Streamlit operations dashboard for the document pipeline."""

from __future__ import annotations

import pandas as pd
import streamlit as st
import altair as alt

from app.database import (
    DatabaseError,
    approve_document,
    create_database_engine,
    dashboard_metrics,
    database_url_from_env,
    initialize_database,
    list_documents,
)

st.set_page_config(
    page_title="Document AI Control Center",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root { --blue:#1479ff; --navy:#082f64; --ice:#eef7ff; }
      .stApp {
        background: linear-gradient(145deg, #f7fbff 0%, #edf6ff 45%, #f9fcff 100%);
        color: #12375f;
      }
      [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f1f8ff 0%, #d9edff 55%, #c9e5ff 100%);
        border-right: 1px solid #b9dcff;
      }
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] p,
      [data-testid="stSidebar"] label,
      [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #12375f !important;
      }
      [data-testid="stSidebar"] [role="group"]:has(input[role="combobox"]) {
        background: rgba(255,255,255,.94) !important;
        border: 1px solid #90c9ff !important;
        border-radius: 12px !important;
        color: #0a3768 !important;
        box-shadow: 0 5px 16px rgba(25, 103, 178, .08);
      }
      [data-testid="stSidebar"] input[role="combobox"],
      [data-testid="stSidebar"] input[role="combobox"] + button {
        background: transparent !important;
      }
      [data-testid="stSidebar"] input[role="combobox"],
      [data-testid="stSidebar"] input[role="combobox"] + button,
      [data-testid="stSidebar"] input[role="combobox"] + button * {
        color: #0a3768 !important;
      }
      [data-testid="stSidebar"] hr { border-color: #afd5f7; }
      .hero {
        padding: 30px 34px; border-radius: 24px; color: white; margin-bottom: 22px;
        background: linear-gradient(120deg, #073a7a 0%, #1479ff 60%, #56b7ff 100%);
        box-shadow: 0 16px 40px rgba(20, 121, 255, .22);
      }
      .hero h1 { margin: 0; font-size: 2.2rem; letter-spacing: -.04em; }
      .hero p { margin: 8px 0 0; opacity: .88; font-size: 1.02rem; }
      [data-testid="stMetric"] {
        background: rgba(255,255,255,.88); border: 1px solid #d7eaff;
        padding: 18px 20px; border-radius: 18px;
        box-shadow: 0 8px 24px rgba(16, 92, 173, .08);
      }
      [data-testid="stMetricLabel"] { color: #426487 !important; }
      [data-testid="stMetricValue"] { color: #073a7a; }
      .section-title { color:#082f64; font-size:1.2rem; font-weight:750; margin:18px 0 8px; }
      .status-pill {
        display:inline-block; padding:5px 10px; border-radius:999px;
        background:#dff0ff; color:#0759aa; font-weight:700; font-size:.8rem;
      }
      div.stButton > button {
        border-radius: 12px; border: 1px solid #82c2ff; color:#0759aa;
        background:white; font-weight:700;
      }
      div.stButton > button:hover { border-color:#1479ff; color:#1479ff; }
      [data-testid="stSidebar"] div.stButton > button {
        min-height: 44px;
        background: linear-gradient(100deg, #0865d5 0%, #218dff 100%) !important;
        border: 0 !important;
        color: #ffffff !important;
        box-shadow: 0 8px 20px rgba(8, 101, 213, .24);
      }
      [data-testid="stSidebar"] div.stButton > button * {
        color: #ffffff !important;
      }
      [data-testid="stSidebar"] div.stButton > button:hover {
        background: linear-gradient(100deg, #0759bd 0%, #1479ff 100%) !important;
        box-shadow: 0 10px 24px rgba(8, 101, 213, .32);
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_engine():
    database_url = database_url_from_env()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return engine


def flatten_document(item: dict) -> dict:
    extracted = item.get("extracted_data") or {}
    return {
        "ID": item["id"],
        "File": item["filename"],
        "Type": item["document_type"] or "—",
        "Status": item["status"],
        "Invoice": extracted.get("invoice_number", "—"),
        "Company": extracted.get("company", "—"),
        "Total": extracted.get("total"),
        "Currency": extracted.get("currency", "—"),
        "Processed": item["processed_at"].strftime("%Y-%m-%d %H:%M"),
    }


def render() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>Document AI Control Center</h1>
          <p>Invoices, automation health and manual review in one calm workspace.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        engine = get_engine()
        metrics = dashboard_metrics(engine)
    except Exception as error:
        st.error(f"Database connection failed: {error}")
        st.stop()

    with st.sidebar:
        st.markdown("## 💠 Control Center")
        st.caption("AI Business Document Pipeline")
        status_filter = st.selectbox(
            "Document status",
            ["all", "processed", "needs_review", "failed"],
        )
        row_limit = st.slider("Recent documents", 10, 200, 50, 10)
        if st.button("↻ Refresh dashboard", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.caption("FastAPI · MySQL · Ollama · n8n")

    cards = st.columns(5)
    cards[0].metric("Total documents", f"{metrics['total_documents']:,}")
    cards[1].metric("Processed", f"{metrics['processed']:,}")
    cards[2].metric("Needs review", f"{metrics['needs_review']:,}")
    cards[3].metric("Failed", f"{metrics['failed']:,}")
    cards[4].metric("Invoice amount", f"{metrics['total_invoice_amount']:,.2f}")

    chart_col, run_col = st.columns([2, 1])
    with chart_col:
        st.markdown('<div class="section-title">Processing health</div>', unsafe_allow_html=True)
        chart_data = pd.DataFrame(
            {
                "Status": ["Processed", "Needs review", "Failed"],
                "Documents": [
                    metrics["processed"],
                    metrics["needs_review"],
                    metrics["failed"],
                ],
            }
        )
        chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusTopLeft=7, cornerRadiusTopRight=7)
            .encode(
                x=alt.X("Status:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Documents:Q", title=None),
                color=alt.Color(
                    "Status:N",
                    scale=alt.Scale(
                        domain=["Processed", "Needs review", "Failed"],
                        range=["#1479ff", "#65b7ff", "#9fcfff"],
                    ),
                    legend=None,
                ),
                tooltip=["Status:N", "Documents:Q"],
            )
            .properties(height=230, background="#ffffff")
            .configure_view(stroke="#d7eaff", fill="#ffffff", cornerRadius=14)
            .configure_axis(
                labelColor="#426487",
                gridColor="#e5f1fb",
                tickColor="#beddf7",
                domain=False,
            )
        )
        st.altair_chart(chart, use_container_width=True)
    with run_col:
        st.markdown('<div class="section-title">Latest activity</div>', unsafe_allow_html=True)
        last_run = metrics["last_processing_run"]
        st.info(
            "No processing runs yet"
            if last_run is None
            else f"Last processing run\n\n**{last_run:%Y-%m-%d %H:%M:%S}**"
        )
        completion = (
            metrics["processed"] / metrics["total_documents"]
            if metrics["total_documents"]
            else 0
        )
        st.write("Processing completion")
        st.progress(completion, text=f"{completion:.0%}")

    selected_status = None if status_filter == "all" else status_filter
    documents = list_documents(engine, status=selected_status, limit=row_limit)
    st.markdown('<div class="section-title">Recent documents</div>', unsafe_allow_html=True)
    if documents:
        frame = pd.DataFrame(flatten_document(item) for item in documents)
        st.dataframe(
            frame,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total": st.column_config.NumberColumn(format="%.2f"),
                "Status": st.column_config.TextColumn(width="small"),
            },
        )
    else:
        st.info("No documents match the selected status.")

    review_items = list_documents(engine, status="needs_review", limit=20)
    st.markdown('<div class="section-title">Manual review queue</div>', unsafe_allow_html=True)
    if not review_items:
        st.success("Review queue is clear.")
    for item in review_items:
        with st.expander(f"#{item['id']} · {item['filename']}"):
            extracted = item.get("extracted_data") or {}
            st.write(
                {
                    "invoice": extracted.get("invoice_number"),
                    "company": extracted.get("company"),
                    "total": extracted.get("total"),
                    "reasons": item.get("reasons", []),
                }
            )
            if st.button("Approve document", key=f"approve-{item['id']}"):
                try:
                    approve_document(engine, item["id"])
                    st.success("Document approved.")
                    st.rerun()
                except DatabaseError as error:
                    st.error(str(error))


if __name__ == "__main__":
    render()
