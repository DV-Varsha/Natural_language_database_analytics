# 📊 Natural Language Database Analytics Agent

An intelligent, production-ready AI analytics agent built with **Python**, **Streamlit**, **SQLite**, **Pandas**, and **Plotly**. Converts natural language business questions into optimized SQL queries, strictly validates execution safety (enforcing read-only access), queries the sales database, and renders interactive tables, executive summaries, and dynamic charts.

---

## 🌟 Key Features

- **🗣️ Natural Language to SQL Translation**: Ask complex sales and revenue questions in plain English. Supports both **Google Gemini** (via `google-genai`) and **OpenAI** (via `openai`).
- **🛡️ AST-Powered Security Validator**: Employs `sqlglot` Abstract Syntax Tree (AST) parsing to guarantee **read-only SELECT** operations. Destructive statements (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`), multi-statement SQL injections, and administrative commands (`PRAGMA`, `ATTACH`) are blocked.
- **🗄️ Relational Sales Database**: Pre-seeded SQLite database with normalized schema (`customers`, `categories`, `products`, `orders`, `order_items`) and realistic sales metrics.
- **📈 Dynamic Interactive Charting**: Automatically inspects DataFrame dimensions and column types to render the optimal Plotly visualization (Bar, Time-Series Line, Donut/Pie, Area, Scatter, or Metric Cards), with manual customization controls.
- **💡 Executive Business Insights**: Automatically synthesizes bulleted findings, top performers, and anomalies from the query result.
- **📥 Data Export**: Instant CSV download for any executed analytical query.

---

## 📂 Project Architecture

```text
natural-language-database-analytics/
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── app.py                    # Streamlit web interface and orchestration
├── src/
│   ├── __init__.py           # Package marker
│   ├── database.py           # SQLite schema, seeding, and execution
│   ├── sql_generator.py      # LLM integration & prompt engineering
│   ├── sql_validator.py      # AST-based SQL security validator
│   └── chart_generator.py    # Automatic & custom Plotly charts
└── tests/
    └── test_components.py    # Unit tests for database, security, and charts
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Virtual Environment
Ensure Python 3.10+ is installed. Create and activate a virtual environment:

```bash
# Windows
py -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Keys
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and specify your preferred LLM provider and API key:
```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Or OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key_here
# OPENAI_MODEL=gpt-4o-mini
```
*(Note: You can also enter or override your API key directly in the Streamlit web sidebar).*

### 4. Run the Application
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🧪 Running Unit Tests

Run the test suite to verify database seeding, SQL validation safety, and chart generation:

```bash
python -m unittest tests/test_components.py
```

---

## 🔒 Security Architecture

The agent implements defense-in-depth SQL validation:
1. **Single-Statement Enforcement**: Queries containing multiple statements (e.g. `; DROP TABLE ...`) are detected and rejected.
2. **AST Root Verification**: Only `Select` and `Union` roots (or `WITH` CTEs resolving to `Select`) are accepted.
3. **Blacklisted AST Nodes**: Recursive tree traversal detects and blocks `Insert`, `Update`, `Delete`, `Drop`, `AlterTable`, `Create`, `Pragma`, `Truncate`, and `Merge`.
4. **Function Sanitization**: Dangerous SQLite functions like `load_extension`, `writefile`, and `readfile` are rejected.

---

## 💡 Example Questions to Try

- *"What are the top 5 best-selling products by total revenue?"*
- *"Show monthly sales and order count trends for 2024."*
- *"What is the total revenue and profit margin across product categories?"*
- *"Show total sales distribution by customer region as a pie chart."*
- *"List the top 5 customers with their total spend and order counts."*
- *"Compare order statuses and their percentage breakdown."*
