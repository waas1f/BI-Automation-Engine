"""Streamlit demo app for the Business Intelligence Automation Engine.

Simple flow: Select Business Type → Upload Data → Analyze → KPIs →
Important Findings → Charts → Download Professional PDF.
"""

import os
import sys
import tempfile

import streamlit as st

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import run_analysis


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BI Automation Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── Styling ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.3rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #6b7280;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        text-align: center;
    }
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a2e;
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .finding-high {
        border-left: 4px solid #ef4444;
        background: #fef2f2;
        padding: 0.75rem 1rem;
        border-radius: 0.375rem;
        margin-bottom: 0.5rem;
    }
    .finding-medium {
        border-left: 4px solid #f59e0b;
        background: #fffbeb;
        padding: 0.75rem 1rem;
        border-radius: 0.375rem;
        margin-bottom: 0.5rem;
    }
    .finding-low {
        border-left: 4px solid #3b82f6;
        background: #eff6ff;
        padding: 0.75rem 1rem;
        border-radius: 0.375rem;
        margin-bottom: 0.5rem;
    }
    .finding-info {
        border-left: 4px solid #10b981;
        background: #ecfdf5;
        padding: 0.75rem 1rem;
        border-radius: 0.375rem;
        margin-bottom: 0.5rem;
    }
    .finding-title {
        font-weight: 600;
        color: #1a1a2e;
        font-size: 0.95rem;
    }
    .finding-detail {
        font-size: 0.85rem;
        color: #4b5563;
        margin-top: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────

st.markdown('<div class="main-header">Business Intelligence Automation Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Upload your data and get instant KPIs, findings, charts, and a professional PDF report.</div>', unsafe_allow_html=True)

st.markdown("---")


# ── Step 1: Select Business Type & Upload ──────────────────────────────────────

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 1. Business Type")
    vertical = st.selectbox(
        "Select your business type",
        options=["wholesale", "retail", "restaurant"],
        format_func=lambda x: x.title(),
        label_visibility="collapsed",
    )
    business_name = st.text_input("Business name", value=f"My {vertical.title()} Business")

with col2:
    st.markdown("### 2. Upload Data")
    uploaded_files = st.file_uploader(
        "Upload CSV or Excel files (you can select multiple files)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) ready for analysis:")
        for f in uploaded_files:
            st.write(f"• {f.name} ({f.size:,} bytes)")

st.markdown("---")


# ── Step 3: Analyze ───────────────────────────────────────────────────────────

if uploaded_files:
    if st.button("Analyze", type="primary", use_container_width=False):
        # Save uploaded files to a temp directory
        tmpdir = tempfile.mkdtemp(prefix="bi_streamlit_")
        file_paths = []
        for uploaded in uploaded_files:
            path = os.path.join(tmpdir, uploaded.name)
            # Read fresh bytes from the UploadedFile and write to disk
            uploaded.seek(0)
            with open(path, "wb") as f:
                f.write(uploaded.read())
            file_paths.append(path)

        output_dir = os.path.join(tmpdir, "reports")
        os.makedirs(output_dir, exist_ok=True)

        with st.spinner("Analyzing data..."):
            result = run_analysis(
                vertical=vertical,
                input_paths=file_paths,
                business_name=business_name,
                output_dir=output_dir,
            )

        if not result.success:
            st.error("Analysis failed:")
            for err in result.errors:
                st.error(f"- {err}")
        else:
            st.session_state["analysis_result"] = result
            st.session_state["business_name"] = business_name
            st.success("Analysis complete!")
            st.rerun()
else:
    st.info("Upload your data files to get started.")


# ── Display results ────────────────────────────────────────────────────────────

if "analysis_result" in st.session_state:
    result = st.session_state["analysis_result"]
    business_name = st.session_state.get("business_name", "Business")

    st.markdown("---")

    # ── KPIs ──────────────────────────────────────────────────────────────
    st.markdown("### Key Metrics")

    for ar in result.context.analysis_results:
        if not ar.available or not ar.kpis:
            continue

        entity_label = ar.entity_type.replace("_", " ").title()
        st.markdown(f"**{entity_label}**")

        kpis = ar.kpis
        # Select the most important KPIs for display
        display_kpis = {}
        for key in ["total_revenue", "total_stock", "total_purchases", "order_count",
                     "transaction_count", "avg_order_value", "avg_transaction_value",
                     "units_sold", "total_items_sold", "unique_customers",
                     "unique_products", "unique_menu_items", "unique_suppliers",
                     "gross_margin_pct", "low_stock_count", "inventory_turnover",
                     "supplier_concentration", "customer_concentration"]:
            if key in kpis:
                display_kpis[key] = kpis[key]

        if display_kpis:
            cols = st.columns(min(len(display_kpis), 4))
            for idx, (key, value) in enumerate(display_kpis.items()):
                col = cols[idx % len(cols)]
                label = key.replace("_", " ").title()
                if isinstance(value, float):
                    if "pct" in key or "concentration" in key:
                        display_val = f"{value:.1f}%"
                    elif abs(value) >= 1_000_000:
                        display_val = f"{value / 1_000_000:.2f}M"
                    elif abs(value) >= 1_000:
                        display_val = f"{value:,.0f}"
                    else:
                        display_val = f"{value:,.2f}"
                else:
                    display_val = f"{value:,}" if isinstance(value, (int, float)) else str(value)

                col.markdown(
                    f'<div class="kpi-card"><div class="kpi-value">{display_val}</div>'
                    f'<div class="kpi-label">{label}</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("")

    # ── Profitability ────────────────────────────────────────────────────
    for ar in result.context.analysis_results:
        if ar.available and ar.profitability:
            prof = ar.profitability
            entity_label = ar.entity_type.replace("_", " ").title()
            st.markdown(f"**{entity_label} Profitability**")

            cols = st.columns(5)
            metrics = [
                ("Revenue", prof.get("total_revenue", 0)),
                ("Cost", prof.get("total_cost", 0)),
                ("Gross Profit", prof.get("gross_profit", 0)),
                ("Margin %", prof.get("gross_margin_pct", 0)),
                ("Cost Basis", prof.get("cost_basis", "N/A")),
            ]
            for idx, (label, value) in enumerate(metrics):
                col = cols[idx]
                if label == "Cost Basis":
                    display_val = str(value).replace("_", " ").title()
                elif label == "Margin %":
                    display_val = f"{value:.1f}%"
                elif isinstance(value, (int, float)):
                    if abs(value) >= 1_000_000:
                        display_val = f"{value / 1_000_000:.2f}M"
                    elif abs(value) >= 1_000:
                        display_val = f"{value:,.0f}"
                    else:
                        display_val = f"{value:,.2f}"
                else:
                    display_val = str(value)

                col.markdown(
                    f'<div class="kpi-card"><div class="kpi-value">{display_val}</div>'
                    f'<div class="kpi-label">{label}</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown("")

    st.markdown("---")

    # ── Important Findings ────────────────────────────────────────────────
    st.markdown("### Important Findings")

    severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    sorted_findings = sorted(
        result.context.findings,
        key=lambda f: severity_order.get(f.severity.value, 4),
    )

    for finding in sorted_findings:
        sev = finding.severity.value
        css_class = f"finding-{sev}"
        type_label = finding.type.value.replace("_", " ").title()

        detail_parts = []
        if finding.value is not None and finding.value != 0:
            if isinstance(finding.value, float):
                if finding.title.lower().endswith("%") or "%" in (finding.comparison or "").lower():
                    detail_parts.append(f"<strong>Value:</strong> {finding.value:.1f}%")
                elif abs(finding.value) >= 1_000_000:
                    detail_parts.append(f"<strong>Value:</strong> {finding.value / 1_000_000:.2f}M")
                elif abs(finding.value) >= 1_000:
                    detail_parts.append(f"<strong>Value:</strong> {finding.value:,.0f}")
                else:
                    detail_parts.append(f"<strong>Value:</strong> {finding.value:,.2f}")
            else:
                detail_parts.append(f"<strong>Value:</strong> {finding.value}")

        if finding.comparison:
            detail_parts.append(f"<strong>Comparison:</strong> {finding.comparison}")
        if finding.explanation:
            detail_parts.append(f"<strong>Why it matters:</strong> {finding.explanation}")
        if finding.recommended_action:
            detail_parts.append(f"<strong>Action:</strong> {finding.recommended_action}")

        detail_html = "<br>".join(detail_parts) if detail_parts else ""

        st.markdown(
            f'<div class="{css_class}">'
            f'<div class="finding-title">{finding.title}</div>'
            f'<div class="finding-detail">{type_label} | Severity: {sev.title()}</div>'
            f'<div class="finding-detail">{detail_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Charts ───────────────────────────────────────────────────────────
    st.markdown("### Charts")

    if result.context.chart_paths:
        cols = st.columns(2)
        for idx, (chart_key, chart_path) in enumerate(result.context.chart_paths.items()):
            col = cols[idx % 2]
            if chart_path and os.path.exists(chart_path):
                title = chart_key.replace("_", " ").title()
                col.image(chart_path, caption=title, use_container_width=True)
    else:
        st.info("No charts available for this dataset.")

    st.markdown("---")

    # ── Download PDF ─────────────────────────────────────────────────────
    st.markdown("### Download Report")

    if result.pdf_path and os.path.exists(result.pdf_path):
        with open(result.pdf_path, "rb") as f:
            pdf_bytes = f.read()

        filename = os.path.basename(result.pdf_path)
        st.download_button(
            label="Download Professional PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            type="primary",
        )

        st.caption(f"Report file: {filename}")

    # ── Data Quality Summary ────────────────────────────────────────────
    if result.context.quality_reports:
        st.markdown("### Data Quality Summary")
        for qr in result.context.quality_reports:
            with st.expander(f"{qr.source}"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Rows (before)", qr.rows_before)
                col2.metric("Rows (after)", qr.rows_after)
                col3.metric("Duplicates detected", qr.duplicates_detected)
                col4.metric("Duplicates removed", qr.duplicates_removed)

                if qr.transformations:
                    st.markdown("**Transformations applied:**")
                    for t in qr.transformations:
                        st.markdown(f"- {t}")
