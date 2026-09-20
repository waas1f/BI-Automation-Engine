# Business Intelligence Automation Engine

A reusable Python engine that transforms messy real-world SMB business data into professional, actionable business intelligence reports. Built around a shared core engine with specialized configurations for wholesale, retail, and restaurant verticals.

## What It Does

Small and medium-sized businesses have data in spreadsheets, CSV exports, and accounting system dumps. These files are rarely clean. This engine:

1. Loads CSV and Excel files (including multi-sheet workbooks)
2. Automatically detects table structure and header rows
3. Cleans messy data (currency symbols, mixed date formats, duplicates, inconsistent categories)
4. Maps columns to a canonical model using aliases and fuzzy matching
5. Validates data quality and generates a quality report
6. Calculates business KPIs, descriptive statistics, time-series trends, and category breakdowns
7. Detects anomalies and generates evidence-based findings
8. Produces a professional PDF report with charts, tables, and recommendations

## Architecture

```
                         CORE ENGINE
                              │
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
       WHOLESALE            RETAIL            RESTAURANT
       CONFIG               CONFIG              CONFIG
          ↓                   ↓                   ↓
   Vertical Analysis    Vertical Analysis   Vertical Analysis
          ↓                   ↓                   ↓
   Vertical Report      Vertical Report     Vertical Report
```

The core engine provides all reusable functionality (loading, cleaning, analytics, charts, report generation). Each vertical adds its own configuration, KPI definitions, business-specific findings, and report structure.

### Project Structure

```
business_intelligence/
├── app/
│   ├── main.py                    # Entry point and pipeline orchestrator
│   ├── core/
│   │   ├── models.py              # Data contracts (LoadedTable, Finding, etc.)
│   │   ├── utils.py               # Shared utilities
│   │   ├── loader.py              # File loading (CSV, XLS, XLSX)
│   │   ├── inspector.py           # Header detection, structural cleanup
│   │   ├── schema_detector.py     # Column type inference
│   │   ├── column_mapper.py       # Canonical column mapping
│   │   ├── cleaner.py             # Numeric, date, text cleaning
│   │   ├── validator.py           # Data quality validation
│   │   ├── analytics.py           # Descriptive stats, time-series, profitability
│   │   ├── anomalies.py           # Anomaly detection (IQR, trend, concentration)
│   │   ├── findings.py            # Structured findings engine
│   │   ├── charts.py              # Chart generation (matplotlib)
│   │   └── report_generator.py    # PDF report generation (ReportLab)
│   ├── ai/
│   │   ├── provider.py            # AI provider interface (local + cloud)
│   │   └── insights.py            # AI commentary generation
│   └── verticals/
│       ├── wholesale/             # config, analysis, report
│       ├── retail/                # config, analysis, report
│       └── restaurant/            # config, analysis, report
├── data/
│   ├── generate_datasets.py       # Synthetic dataset generator
│   ├── sample/                    # Wholesale, retail, restaurant datasets
│   └── test/                      # Messy and edge-case datasets
├── reports/                       # Generated PDF reports and chart assets
├── tests/
│   └── test_pipeline.py           # Unit and end-to-end tests
├── requirements.txt
└── README.md
```

## Supported File Types

- CSV (.csv)
- Excel (.xls, .xlsx, .xlsm)

## Supported Verticals

### Wholesale
For distributors, wholesalers, suppliers, and trading businesses. Analyzes sales, products, customers, inventory, and purchases. Detects customer concentration, low-margin products, declining products, low-stock items, and supplier concentration.

### Retail
For supermarkets, grocery stores, convenience stores, and general retailers. Analyzes sales, product/category performance, inventory, and profitability. Detects fast/slow movers, excess stock, and category margin differences.

### Restaurant
For restaurants and food service businesses. Analyzes revenue, menu performance, category breakdowns, and profitability. Detects peak sales days, best-selling items, underperforming menu items, and margin issues.

## Installation

```bash
cd business_intelligence
pip install -r requirements.txt
```

Requirements: Python 3.10+, pandas, numpy, matplotlib, openpyxl, reportlab, xlrd, streamlit, flask

## Usage

### Command Line

```bash
# Wholesale analysis with multiple files
python -m app.main wholesale data/sample/wholesale_sales.csv data/sample/wholesale_inventory.csv data/sample/wholesale_purchases.csv --name "Acme Distribution" --output reports

# Retail analysis
python -m app.main retail data/sample/retail_sales.csv data/sample/retail_inventory.csv --name "City Mart" --output reports

# Restaurant analysis
python -m app.main restaurant data/sample/restaurant_sales.csv --name "Bella Cucina" --output reports

# With AI commentary enabled
python -m app.main wholesale data/sample/wholesale_sales.csv --name "Acme" --ai --output reports
```

### Streamlit Web UI

```bash
streamlit run streamlit_app.py
```

The Streamlit app provides a clean demo interface:
1. Select business type (Wholesale, Retail, or Restaurant)
2. Upload one or more data files (CSV or Excel) — files accumulate so you can add multiple files in separate selections
3. Click Analyze
4. View KPIs, findings, charts, and data quality summary
5. Download a professional PDF report

### Deploy to Streamlit Cloud

1. Push this project to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo and select `streamlit_app.py` as the entry point
4. Set the Python version to 3.10+
5. Deploy — Streamlit Cloud will install `requirements.txt` automatically

### Python API

```python
from app.main import run_analysis

result = run_analysis(
    vertical="wholesale",
    input_paths=["data/sample/wholesale_sales.csv", "data/sample/wholesale_inventory.csv"],
    business_name="Acme Distribution",
    output_dir="reports",
    use_ai=False,
)

print(f"Report: {result.pdf_path}")
```

## Sample Workflow

1. Select a vertical (wholesale, retail, or restaurant)
2. Provide one or more business data files (CSV or Excel)
3. The engine automatically inspects, cleans, and validates the data
4. Business KPIs and analytics are calculated
5. Findings and anomalies are identified
6. A professional PDF report is generated with charts, tables, and recommendations

## Messy Data Handling

The engine is designed to handle real-world SMB data exports:

- **Title rows**: Detects actual header row when data starts several rows down
- **Blank rows**: Removes empty and near-empty rows
- **Footer/summary rows**: Detects and removes "Total", "Subtotal", "Grand Total" rows
- **Repeated headers**: Removes duplicate header rows within the data
- **Currency symbols**: Parses `$1,250.00`, `1250 USD`, `€1.250,00`
- **Mixed date formats**: Supports ISO, European, US, and named-month formats
- **Inconsistent categories**: Detects case-variant duplicates (e.g., "ABC Supermarket" vs "abc supermarket")
- **Duplicate records**: Detects and removes exact duplicates
- **Missing values**: Reports percentage missing per column
- **Unnamed columns**: Assigns placeholder names

When a transformation is uncertain, the engine flags it in the data quality report rather than silently corrupting data.

## AI Layer

The AI layer is optional and modular. The system works fully without any external API key.

- **LocalAIProvider**: Generates deterministic template-based commentary from structured metrics. Always available.
- **CloudAIProvider**: Placeholder for external AI API integration. Uses environment variables for API keys. Falls back to local provider when no key is set.

The AI receives structured analytical results (KPIs, findings), never raw datasets. It cannot invent facts — it only explains metrics that the deterministic engine has already calculated.

## Testing

```bash
# Generate synthetic datasets
python data/generate_datasets.py

# Run tests
python -m pytest tests/test_pipeline.py -v
```

### Test Datasets

- **clean_sales.csv**: Perfectly structured data
- **messy_sales.csv**: Title rows, blank rows, inconsistent formatting, duplicates, mixed currency/date formats
- **edge_case_sales.csv**: Zero revenue, negative values, missing costs, malformed dates, empty columns
- **wholesale_*.csv**: Sales, inventory, and purchase data with customer concentration, low-margin products, declining products, low-stock items, supplier concentration
- **retail_*.csv**: Sales and inventory with fast/slow movers, excess stock, category margin differences
- **restaurant_*.csv**: Sales and inventory with peak days, best-selling items, underperforming items

## Limitations

- Requires structured tabular data (CSV or Excel); does not parse PDFs or scanned documents
- Does not include user authentication, billing, or multi-tenant architecture
- AI commentary uses deterministic templates by default; cloud AI integration requires an API key
- Cannot invent metrics when source data is missing (by design)

## Future Improvements

- Additional verticals (e.g., manufacturing, services, healthcare)
- Real-time data connectors (accounting systems, POS systems)
- Trend forecasting and predictive analytics
- Multi-currency support with exchange rate conversion
- Automated data refresh and scheduled report generation
