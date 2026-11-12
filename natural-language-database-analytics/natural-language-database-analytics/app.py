"""
Natural Language Database Analytics Agent - Main Streamlit Application.

Interactive analytics dashboard powered by:
- SQLite for sales relational database
- Google Gemini / OpenAI for Natural Language to SQL translation
- sqlglot for strict read-only AST query validation
- Pandas & Plotly for interactive data exploration and charting
"""

from __future__ import annotations

import os
import time
from typing import Optional
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load local environment variables from .env
load_dotenv()

from src.database import (
    DEFAULT_DB_PATH,
    init_db,
    get_schema_ddl,
    get_schema_metadata,
    execute_query,
    get_sample_rows,
)
from src.sql_validator import validate_sql
from src.sql_generator import generate_sql, generate_summary
from src.chart_generator import (
    auto_generate_chart,
    create_bar_chart,
    create_line_chart,
    create_pie_chart,
    create_area_chart,
    create_scatter_chart,
)

# ---------------------------------------------------------
# Streamlit Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="DataPulse AI - NL Database Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.3rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .status-card {
        padding: 0.8rem 1rem;
        border-radius: 8px;
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        margin-bottom: 0.8rem;
    }
    .sql-badge-safe {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        background-color: #DCFCE7;
        color: #166534;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .sql-badge-unsafe {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        background-color: #FEE2E2;
        color: #991B1B;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Initialize State and Database
# ---------------------------------------------------------
if "db_initialized" not in st.session_state:
    db_status = init_db(DEFAULT_DB_PATH)
    st.session_state.db_initialized = True
    st.session_state.db_status = db_status

if "history" not in st.session_state:
    st.session_state.history = []

if "current_question" not in st.session_state:
    st.session_state.current_question = ""


# ---------------------------------------------------------
# Sidebar Configuration
# ---------------------------------------------------------
with st.sidebar:
    st.title("⚙️ Analytics Settings")

    # LLM Settings Section
    st.subheader("🤖 LLM Provider")
    provider_choice = st.selectbox(
        "Choose Model Provider",
        options=["Gemini (Google)", "OpenAI"],
        index=0 if os.getenv("LLM_PROVIDER", "gemini").lower() == "gemini" else 1,
    )
    provider_code = "gemini" if "Gemini" in provider_choice else "openai"

    if provider_code == "gemini":
        default_key = os.getenv("GEMINI_API_KEY", "")
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=default_key,
            help="Get your API key at https://aistudio.google.com/app/apikey",
        )
        model_name = st.selectbox(
            "Model",
            options=["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
            index=0,
        )
    else:
        default_key = os.getenv("OPENAI_API_KEY", "")
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=default_key,
            help="Get your API key at https://platform.openai.com/api-keys",
        )
        model_name = st.selectbox(
            "Model",
            options=["gpt-4o-mini", "gpt-4o"],
            index=0,
        )

    st.markdown("---")

    # Database Schema & Status Section
    st.subheader("🗄️ Database Management")
    metadata = get_schema_metadata(DEFAULT_DB_PATH)
    total_records = sum(info["row_count"] for info in metadata.values())

    st.markdown(
        f"""
        <div class="status-card">
            <b>Database:</b> SQLite (<code>sales.db</code>)<br>
            <b>Tables:</b> {len(metadata)}<br>
            <b>Total Records:</b> {total_records:,}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔄 Reset / Re-Seed Database", use_container_width=True):
        with st.spinner("Rebuilding database with fresh sample sales records..."):
            init_db(DEFAULT_DB_PATH, force=True)
            st.success("Database successfully re-seeded!")
            st.rerun()

    # Schema Explorer Expander
    with st.expander("🔍 View Database Schema", expanded=False):
        for table, info in metadata.items():
            st.markdown(f"**Table: `{table}`** ({info['row_count']} rows)")
            col_df = pd.DataFrame(info["columns"])
            st.dataframe(col_df[["name", "type", "pk", "notnull"]], hide_index=True, use_container_width=True)
            if st.checkbox(f"Show sample rows for `{table}`", key=f"sample_{table}"):
                sample_data = get_sample_rows(table, limit=3, db_path=DEFAULT_DB_PATH)
                st.dataframe(sample_data, hide_index=True, use_container_width=True)


# ---------------------------------------------------------
# Main UI Header
# ---------------------------------------------------------
st.markdown('<div class="main-title">📊 Natural Language Database Analytics Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Ask analytical questions about your sales data in plain English. '
    'The agent generates SQL, validates query safety, runs against SQLite, and produces tables, insights, and interactive charts.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Example Prompt Quick-Pills
# ---------------------------------------------------------
st.markdown("##### 💡 Try an Example Question:")
example_prompts = [
    "What are the top 5 best-selling products by total revenue?",
    "Show monthly sales and order count trends for 2024",
    "What is the total revenue and profit across product categories?",
    "Show total sales distribution by customer region",
    "List the top 5 customers with their total spend and order counts",
    "Compare order statuses and their percentage breakdown",
]

cols = st.columns(3)
for idx, prompt_text in enumerate(example_prompts):
    with cols[idx % 3]:
        if st.button(f"📌 {prompt_text}", key=f"ex_{idx}", use_container_width=True):
            st.session_state.current_question = prompt_text
            st.rerun()

# ---------------------------------------------------------
# Query Input Box
# ---------------------------------------------------------
with st.container():
    query_input = st.text_area(
        "Enter your question about sales data:",
        value=st.session_state.current_question,
        placeholder="e.g., Which product category generated the highest profit in the West region?",
        height=90,
    )
    run_col, clear_col, _ = st.columns([1.2, 1, 6])
    run_clicked = run_col.button("🚀 Run Analysis", type="primary", use_container_width=True)
    if clear_col.button("🗑️ Clear", use_container_width=True):
        st.session_state.current_question = ""
        st.rerun()


# ---------------------------------------------------------
# Execution & Analysis Engine
# ---------------------------------------------------------
if run_clicked and query_input.strip():
    question = query_input.strip()
    st.session_state.current_question = question

    # Step 1: Validate API Key
    if not api_key or api_key.strip() == "" or "your_" in api_key.lower():
        st.error(
            f"⚠️ **Missing API Key**: Please enter a valid {provider_choice} API key in the left sidebar "
            f"or configure `{provider_code.upper()}_API_KEY` in your `.env` file to enable SQL generation."
        )
    else:
        with st.status("🔍 Processing Analytical Query...", expanded=True) as status_box:
            # 1. Fetch schema DDL
            st.write("Extracting database schema and relational context...")
            schema_ddl = get_schema_ddl(DEFAULT_DB_PATH)

            # 2. Generate SQL via LLM
            st.write(f"Generating SQLite query via {provider_choice} ({model_name})...")
            start_gen_time = time.time()
            try:
                raw_sql = generate_sql(
                    question=question,
                    schema_ddl=schema_ddl,
                    provider=provider_code,
                    api_key=api_key,
                    model=model_name,
                )
            except Exception as e:
                status_box.update(label="❌ SQL Generation Failed", state="error")
                st.error(f"Error during SQL generation: {str(e)}")
                st.stop()

            # 3. Security Validation
            st.write("Verifying query safety with AST parser (read-only enforcement)...")
            is_valid, sanitized_sql, error_msg = validate_sql(raw_sql)

            if not is_valid:
                status_box.update(label="🚨 Query Blocked by Safety Validator", state="error")
                st.markdown('<div class="sql-badge-unsafe">❌ Prohibited Query Blocked</div>', unsafe_allow_html=True)
                st.error(
                    f"**Security Alert:** The generated SQL query was rejected because it violates the read-only policy.\n\n"
                    f"**Reason:** {error_msg}\n\n"
                    f"```sql\n{raw_sql}\n```"
                )
                st.stop()

            # 4. Execute Query
            st.write("Executing validated query against SQLite...")
            start_exec_time = time.time()
            try:
                results_df = execute_query(sanitized_sql, DEFAULT_DB_PATH)
                exec_duration = (time.time() - start_exec_time) * 1000
            except Exception as e:
                status_box.update(label="❌ Query Execution Error", state="error")
                st.error(f"SQLite execution failed: {str(e)}")
                st.code(sanitized_sql, language="sql")
                st.stop()

            # 5. Generate Natural Language Summary / Insights
            st.write("Synthesizing executive summary and insights...")
            insights = generate_summary(
                question=question,
                sql_query=sanitized_sql,
                df=results_df,
                provider=provider_code,
                api_key=api_key,
                model=model_name,
            )

            status_box.update(label="✅ Analysis Complete!", state="complete", expanded=False)

        # Store in session state for history
        st.session_state.last_result = {
            "question": question,
            "sql": sanitized_sql,
            "df": results_df,
            "insights": insights,
            "exec_duration_ms": exec_duration,
        }

# ---------------------------------------------------------
# Results Display
# ---------------------------------------------------------
if "last_result" in st.session_state:
    res = st.session_state.last_result
    df = res["df"]
    sql = res["sql"]
    insights = res["insights"]
    duration = res["exec_duration_ms"]

    st.markdown("---")
    st.markdown('<div class="sql-badge-safe">🛡️ Safe Read-Only Query Verified</div>', unsafe_allow_html=True)

    # Top KPI Metrics row
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Total Records Found", f"{len(df):,}")
    metric_col2.metric("Execution Latency", f"{duration:.1f} ms")
    
    # Optional Third Metric if numeric column exists
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not c.lower().endswith("_id")]
    if num_cols:
        main_metric = num_cols[0]
        metric_col3.metric(f"Total {main_metric.replace('_', ' ').title()}", f"{df[main_metric].sum():,.2f}")
    else:
        metric_col3.metric("Output Attributes", f"{len(df.columns)}")

    # Main Analysis Tabs
    tab_chart, tab_data, tab_summary, tab_sql = st.tabs([
        "📊 Interactive Chart",
        "📋 Data Table",
        "💡 Business Insights",
        "🔍 SQL Query Details",
    ])

    # Tab 1: Chart Generation
    with tab_chart:
        if df.empty:
            st.info("No data returned to plot.")
        else:
            auto_fig, chart_desc = auto_generate_chart(df, question=res["question"])

            # Manual Chart Customizer Controls
            with st.expander("🛠️ Chart Options & Customizer", expanded=False):
                ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns(4)
                chart_type = ctrl_col1.selectbox("Chart Type", ["Auto Detect", "Bar Chart", "Line Chart", "Donut/Pie Chart", "Area Chart", "Scatter Plot"])
                available_cols = list(df.columns)
                x_axis = ctrl_col2.selectbox("X-Axis", options=available_cols, index=0)
                y_options = [c for c in available_cols if c != x_axis] or available_cols
                y_axis = ctrl_col3.selectbox("Y-Axis", options=y_options, index=0)
                color_options = [None] + available_cols
                color_col = ctrl_col4.selectbox("Color / Group By", options=color_options, index=0)

            # Determine figure to display
            display_fig = None
            if chart_type == "Auto Detect":
                display_fig = auto_fig
                if auto_fig:
                    st.caption(f"🤖 Automatic selection: **{chart_desc}**")
            elif chart_type == "Bar Chart":
                display_fig = create_bar_chart(df, x_axis, y_axis, color_col=color_col)
            elif chart_type == "Line Chart":
                display_fig = create_line_chart(df, x_axis, y_axis, color_col=color_col)
            elif chart_type == "Donut/Pie Chart":
                display_fig = create_pie_chart(df, x_axis, y_axis)
            elif chart_type == "Area Chart":
                display_fig = create_area_chart(df, x_axis, y_axis, color_col=color_col)
            elif chart_type == "Scatter Plot":
                display_fig = create_scatter_chart(df, x_axis, y_axis, color_col=color_col)

            if display_fig:
                st.plotly_chart(display_fig, use_container_width=True)
            else:
                st.info("The returned data is not suitable for the selected chart configuration.")

    # Tab 2: Tabular Data Table
    with tab_data:
        st.dataframe(df, use_container_width=True)
        # CSV Download Button
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv_data,
            file_name="sales_query_result.csv",
            mime="text/csv",
        )

    # Tab 3: Summary & Insights
    with tab_summary:
        st.markdown("### 💡 Executive Insights")
        st.markdown(insights)

    # Tab 4: SQL Details
    with tab_sql:
        st.markdown("### 📝 Generated & Validated SQL")
        st.code(sql, language="sql")
        st.markdown(
            """
            > **Security Validation**:
            > - Passed AST parsing (verified strictly single statement).
            > - Permitted root operation: `SELECT` / `WITH`.
            > - Zero data modification or administrative keywords detected.
            """
        )
