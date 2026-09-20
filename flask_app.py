"""Flask demo app for the Business Intelligence Automation Engine.

Simple HTTP-only flow that works through proxies:
Select Business Type → Upload Data → Analyze → KPIs → Findings → Charts → Download PDF.
"""

import os
import sys
import tempfile
import shutil
import uuid

from flask import Flask, request, render_template_string, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import run_analysis

app = Flask(__name__)
app.secret_key = "demo-bi-engine"

# Persistent temp directory for session data
DATA_DIR = tempfile.mkdtemp(prefix="bi_demo_")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BI Automation Engine</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #1a1a2e; line-height: 1.6; }
        .container { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem; }
        .header { text-align: center; margin-bottom: 2rem; }
        .header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.3rem; }
        .header p { color: #6b7280; font-size: 1rem; }
        .card { background: white; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .upload-area { border: 2px dashed #d1d5db; border-radius: 0.5rem; padding: 2rem; text-align: center; margin-bottom: 1rem; }
        .upload-area:hover { border-color: #3b82f6; }
        .form-row { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
        .form-group { flex: 1; min-width: 200px; }
        label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.3rem; color: #4b5563; }
        select, input[type="text"] { width: 100%; padding: 0.6rem 0.8rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.95rem; }
        .btn { display: inline-block; padding: 0.7rem 2rem; border: none; border-radius: 0.375rem; font-size: 1rem; font-weight: 600; cursor: pointer; text-decoration: none; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-download { background: #10b981; color: white; }
        .btn-download:hover { background: #059669; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
        .kpi-card { background: #f8f9fa; border-radius: 0.5rem; padding: 1rem; text-align: center; }
        .kpi-value { font-size: 1.4rem; font-weight: 700; color: #1a1a2e; }
        .kpi-label { font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
        .section-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #e5e7eb; }
        .entity-label { font-size: 1.1rem; font-weight: 600; margin: 1rem 0 0.5rem; }
        .finding { border-left: 4px solid; padding: 0.75rem 1rem; border-radius: 0.375rem; margin-bottom: 0.75rem; }
        .finding-high { border-color: #ef4444; background: #fef2f2; }
        .finding-medium { border-color: #f59e0b; background: #fffbeb; }
        .finding-low { border-color: #3b82f6; background: #eff6ff; }
        .finding-info { border-color: #10b981; background: #ecfdf5; }
        .finding-title { font-weight: 600; font-size: 0.95rem; }
        .finding-detail { font-size: 0.85rem; color: #4b5563; margin-top: 0.25rem; }
        .finding-detail strong { color: #1a1a2e; }
        .chart-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(450px, 1fr)); gap: 1rem; }
        .chart-item { text-align: center; }
        .chart-item img { max-width: 100%; border-radius: 0.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .chart-item .chart-title { font-size: 0.85rem; color: #6b7280; margin-top: 0.3rem; }
        .quality-item { background: #f8f9fa; border-radius: 0.5rem; padding: 1rem; margin-bottom: 0.75rem; }
        .quality-item summary { font-weight: 600; cursor: pointer; }
        .quality-metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 0.5rem; margin: 0.75rem 0; }
        .quality-metric { text-align: center; }
        .quality-metric .val { font-weight: 700; font-size: 1.1rem; }
        .quality-metric .lbl { font-size: 0.75rem; color: #6b7280; }
        .transformations { font-size: 0.85rem; color: #4b5563; margin-top: 0.5rem; }
        .transformations li { margin-left: 1.5rem; }
        .error { background: #fef2f2; border-left: 4px solid #ef4444; padding: 0.75rem 1rem; border-radius: 0.375rem; margin-bottom: 1rem; }
        .divider { border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }
        .file-list { font-size: 0.85rem; color: #6b7280; margin-top: 0.5rem; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Business Intelligence Automation Engine</h1>
        <p>Upload your data and get instant KPIs, findings, charts, and a professional PDF report.</p>
    </div>

    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}

    <div class="card">
        <form method="POST" action="analyze" enctype="multipart/form-data">
            <div class="form-row">
                <div class="form-group">
                    <label for="vertical">Business Type</label>
                    <select name="vertical" id="vertical">
                        <option value="wholesale">Wholesale</option>
                        <option value="retail">Retail</option>
                        <option value="restaurant">Restaurant</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="business_name">Business Name</label>
                    <input type="text" name="business_name" id="business_name" value="My Business">
                </div>
            </div>
            <div class="form-group">
                <label for="files">Upload Data Files (CSV or Excel)</label>
                <div class="upload-area">
                    <input type="file" name="files" id="files" multiple accept=".csv,.xlsx,.xls">
                    <p style="margin-top:0.5rem; font-size:0.85rem; color:#6b7280;">Drag files here or click to browse. Upload sales, inventory, and purchases files.</p>
                </div>
            </div>
            <button type="submit" class="btn btn-primary">Analyze</button>
        </form>
    </div>

    {% if session_id %}
    <div class="divider"></div>

    {% if errors %}
    <div class="error">
        {% for err in errors %}
        <div>{{ err }}</div>
        {% endfor %}
    </div>
    {% endif %}

    {% if result %}
    <!-- KPIs -->
    <div class="card">
        <div class="section-title">Key Metrics</div>
        {% for ar in result.context.analysis_results %}
            {% if ar.available and ar.kpis %}
                <div class="entity-label">{{ ar.entity_type | replace('_', ' ') | title }}</div>
                <div class="kpi-grid">
                    {% for key, value in ar.kpis.items() %}
                        {% if key in display_kpis %}
                        <div class="kpi-card">
                            <div class="kpi-value">{{ value | format_kpi }}</div>
                            <div class="kpi-label">{{ key | replace('_', ' ') | title }}</div>
                        </div>
                        {% endif %}
                    {% endfor %}
                </div>
            {% endif %}
        {% endfor %}

        {% for ar in result.context.analysis_results %}
            {% if ar.available and ar.profitability %}
                {% set prof = ar.profitability %}
                <div class="entity-label">{{ ar.entity_type | replace('_', ' ') | title }} Profitability</div>
                <div class="kpi-grid">
                    <div class="kpi-card"><div class="kpi-value">{{ prof.total_revenue | format_currency }}</div><div class="kpi-label">Revenue</div></div>
                    <div class="kpi-card"><div class="kpi-value">{{ prof.total_cost | format_currency }}</div><div class="kpi-label">Cost</div></div>
                    <div class="kpi-card"><div class="kpi-value">{{ prof.gross_profit | format_currency }}</div><div class="kpi-label">Gross Profit</div></div>
                    <div class="kpi-card"><div class="kpi-value">{{ '%.1f' % prof.gross_margin_pct }}%</div><div class="kpi-label">Margin %</div></div>
                    <div class="kpi-card"><div class="kpi-value">{{ prof.get('cost_basis', 'N/A') | replace('_', ' ') | title }}</div><div class="kpi-label">Cost Basis</div></div>
                </div>
            {% endif %}
        {% endfor %}
    </div>

    <!-- Findings -->
    <div class="card">
        <div class="section-title">Important Findings</div>
        {% for finding in findings %}
            <div class="finding finding-{{ finding.severity.value }}">
                <div class="finding-title">{{ finding.title }}</div>
                <div class="finding-detail">
                    {{ finding.type.value | replace('_', ' ') | title }} | Severity: {{ finding.severity.value | title }}
                </div>
                <div class="finding-detail">
                    {% if finding.value is not none and finding.value != 0 %}
                        <strong>Value:</strong> {{ finding.value | format_kpi }}<br>
                    {% endif %}
                    {% if finding.comparison %}<strong>Comparison:</strong> {{ finding.comparison }}<br>{% endif %}
                    {% if finding.explanation %}<strong>Why it matters:</strong> {{ finding.explanation }}<br>{% endif %}
                    {% if finding.recommended_action %}<strong>Action:</strong> {{ finding.recommended_action }}{% endif %}
                </div>
            </div>
        {% endfor %}
    </div>

    <!-- Charts -->
    <div class="card">
        <div class="section-title">Charts</div>
        {% if chart_urls %}
        <div class="chart-grid">
            {% for chart_key, chart_url in chart_urls.items() %}
            <div class="chart-item">
                <img src="{{ chart_url }}" alt="{{ chart_key | replace('_', ' ') | title }}">
                <div class="chart-title">{{ chart_key | replace('_', ' ') | title }}</div>
            </div>
        {% endfor %}
        </div>
        {% else %}
        <p style="color:#6b7280;">No charts available for this dataset.</p>
        {% endif %}
    </div>

    <!-- Download PDF -->
    <div class="card" style="text-align:center;">
        <a href="download/{{ session_id }}" class="btn btn-download">Download Professional PDF Report</a>
        <p class="file-list">Report file: {{ pdf_filename }}</p>
    </div>

    <!-- Data Quality -->
    {% if result.context.quality_reports %}
    <div class="card">
        <div class="section-title">Data Quality Summary</div>
        {% for qr in result.context.quality_reports %}
        <details class="quality-item">
            <summary>{{ qr.source }}</summary>
            <div class="quality-metrics">
                <div class="quality-metric"><div class="val">{{ qr.rows_before }}</div><div class="lbl">Rows (before)</div></div>
                <div class="quality-metric"><div class="val">{{ qr.rows_after }}</div><div class="lbl">Rows (after)</div></div>
                <div class="quality-metric"><div class="val">{{ qr.duplicates_detected }}</div><div class="lbl">Duplicates detected</div></div>
                <div class="quality-metric"><div class="val">{{ qr.duplicates_removed }}</div><div class="lbl">Duplicates removed</div></div>
            </div>
            {% if qr.transformations %}
            <div class="transformations">
                <strong>Transformations applied:</strong>
                <ul>
                    {% for t in qr.transformations %}
                    <li>{{ t }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </details>
        {% endfor %}
    </div>
    {% endif %}

    {% endif %}
    {% endif %}
</div>
</body>
</html>"""


# ── Jinja filters ────────────────────────────────────────────────────────────

DISPLAY_KPI_KEYS = {
    "total_revenue", "total_stock", "total_purchases", "order_count",
    "transaction_count", "avg_order_value", "avg_transaction_value",
    "units_sold", "total_items_sold", "unique_customers",
    "unique_products", "unique_menu_items", "unique_suppliers",
    "gross_margin_pct", "low_stock_count", "inventory_turnover",
    "supplier_concentration", "customer_concentration",
}


def format_kpi(value):
    if isinstance(value, float):
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif abs(value) >= 1_000:
            return f"{value:,.0f}"
        else:
            return f"{value:,.2f}"
    elif isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def format_currency(value):
    if isinstance(value, (int, float)):
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif abs(value) >= 1_000:
            return f"${value:,.0f}"
        else:
            return f"${value:,.2f}"
    return str(value)


app.jinja_env.filters['format_kpi'] = format_kpi
app.jinja_env.filters['format_currency'] = format_currency


# ── Routes ────────────────────────────────────────────────────────────────────

# In-memory session storage
SESSIONS = {}


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/analyze", methods=["POST"])
def analyze():
    vertical = request.form.get("vertical", "wholesale")
    business_name = request.form.get("business_name", "My Business")
    uploaded_files = request.files.getlist("files")

    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        return render_template_string(HTML_TEMPLATE, error="Please upload at least one file.")

    # Create a unique session directory
    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(DATA_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Save uploaded files
    file_paths = []
    for uploaded in uploaded_files:
        if uploaded.filename:
            filename = secure_filename(uploaded.filename)
            path = os.path.join(session_dir, filename)
            uploaded.save(path)
            file_paths.append(path)

    output_dir = os.path.join(session_dir, "reports")
    os.makedirs(output_dir, exist_ok=True)

    result = run_analysis(
        vertical=vertical,
        input_paths=file_paths,
        business_name=business_name,
        output_dir=output_dir,
    )

    if not result.success:
        return render_template_string(
            HTML_TEMPLATE, session_id=session_id, errors=result.errors
        )

    # Build chart URLs
    chart_urls = {}
    if result.context.chart_paths:
        for chart_key, chart_path in result.context.chart_paths.items():
            if chart_path and os.path.exists(chart_path):
                # Copy chart to a URL-accessible location
                chart_filename = os.path.basename(chart_path)
                chart_url = f"chart/{session_id}/{chart_filename}"
                chart_urls[chart_key] = chart_url

    # Sort findings by severity
    severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    sorted_findings = sorted(
        result.context.findings,
        key=lambda f: severity_order.get(f.severity.value, 4),
    )

    # Store in session
    SESSIONS[session_id] = {
        "result": result,
        "output_dir": output_dir,
    }

    pdf_filename = os.path.basename(result.pdf_path) if result.pdf_path else ""

    return render_template_string(
        HTML_TEMPLATE,
        session_id=session_id,
        result=result,
        findings=sorted_findings,
        chart_urls=chart_urls,
        pdf_filename=pdf_filename,
        display_kpis=DISPLAY_KPI_KEYS,
    )


@app.route("/chart/<session_id>/<filename>")
def chart(session_id, filename):
    session = SESSIONS.get(session_id)
    if not session:
        return "Not found", 404
    chart_path = os.path.join(session["output_dir"], "assets", filename)
    if not os.path.exists(chart_path):
        return "Not found", 404
    return send_file(chart_path, mimetype="image/png")


@app.route("/download/<session_id>")
def download(session_id):
    session = SESSIONS.get(session_id)
    if not session:
        return "Not found", 404
    result = session["result"]
    if not result.pdf_path or not os.path.exists(result.pdf_path):
        return "Not found", 404
    return send_file(
        result.pdf_path,
        as_attachment=True,
        download_name=os.path.basename(result.pdf_path),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
