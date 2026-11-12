"""
Chart Generation Module for Natural Language Database Analytics Agent.

Inspects Pandas DataFrame results and generates interactive Plotly visualizations
(Bar, Line, Pie/Donut, Area, Scatter, and Metric Indicators) with automated
chart type detection and manual override support.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple, List, Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# Brand Color Palette
PRIMARY_COLOR = "#2563EB"   # Modern Indigo/Blue
PALETTE = px.colors.qualitative.Prism


def _is_date_col(series: pd.Series) -> bool:
    """Check if a column contains dates or timestamps."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    col_name = str(series.name).lower().strip()

    # If it's numeric, only consider it a date if the column name is specifically 'year'
    if pd.api.types.is_numeric_dtype(series):
        if col_name in ["year", "order_year", "yr"]:
            non_null = series.dropna()
            if not non_null.empty and non_null.min() >= 1900 and non_null.max() <= 2100:
                return True
        return False

    # For string/object columns, test sample values against date patterns
    sample = series.dropna().head(10).astype(str)
    if sample.empty:
        return False

    # Regex matches: YYYY-MM-DD, YYYY-MM, YYYY/MM/DD, etc.
    date_pattern = re.compile(r"^\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?$")
    if all(date_pattern.match(val.strip()) for val in sample):
        return True

    # Also check if pandas can parse them as dates
    if any(k in col_name for k in ["date", "month", "period", "timestamp"]):
        try:
            pd.to_datetime(sample)
            return True
        except Exception:
            pass

    return False


def _classify_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Classify DataFrame columns into date, categorical, and numeric types."""
    date_cols = []
    cat_cols = []
    num_cols = []

    for col in df.columns:
        if _is_date_col(df[col]):
            date_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            # Check if this integer looks like an ID
            col_lower = str(col).lower()
            if col_lower.endswith("_id") or col_lower == "id":
                cat_cols.append(col)
            else:
                num_cols.append(col)
        else:
            cat_cols.append(col)

    return {
        "date": date_cols,
        "categorical": cat_cols,
        "numeric": num_cols,
    }


def create_metric_card(df: pd.DataFrame) -> go.Figure:
    """Render a single aggregated value as an executive KPI indicator."""
    val = df.iloc[0, 0]
    col_name = str(df.columns[0]).replace("_", " ").title()

    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="number",
        value=val,
        title={"text": col_name, "font": {"size": 22, "color": "#475569"}},
        number={
            "font": {"size": 48, "color": "#1E293B", "family": "Arial"},
            "valueformat": ",.2f" if isinstance(val, (float, int)) and not isinstance(val, bool) else "",
        }
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=20, r=20, t=40, b=20),
        template="plotly_white",
    )
    return fig


def create_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    barmode: str = "group",
    title: Optional[str] = None,
    horizontal: bool = False,
) -> go.Figure:
    """Generate a modern styled bar chart."""
    display_title = title or f"{y_col.replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}"

    if horizontal:
        fig = px.bar(
            df,
            x=y_col,
            y=x_col,
            color=color_col,
            orientation="h",
            title=display_title,
            barmode=barmode,
            color_discrete_sequence=PALETTE,
            text_auto=".2s",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        fig = px.bar(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            title=display_title,
            barmode=barmode,
            color_discrete_sequence=PALETTE,
            text_auto=".2s",
        )
        fig.update_layout(xaxis={"categoryorder": "total descending"})

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(family="sans-serif", size=13),
        title_font=dict(size=18, color="#1E293B"),
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=y_col.replace("_", " ").title(),
    )
    return fig


def create_line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """Generate a clean time series or trend line chart."""
    display_title = title or f"Trend of {y_col.replace('_', ' ').title()} over {x_col.replace('_', ' ').title()}"
    df_sorted = df.sort_values(by=x_col)

    fig = px.line(
        df_sorted,
        x=x_col,
        y=y_col,
        color=color_col,
        title=display_title,
        markers=True,
        color_discrete_sequence=PALETTE,
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(family="sans-serif", size=13),
        title_font=dict(size=18, color="#1E293B"),
        xaxis_title=x_col.replace("_", " ").title(),
        yaxis_title=y_col.replace("_", " ").title(),
    )
    return fig


def create_pie_chart(
    df: pd.DataFrame,
    names_col: str,
    values_col: str,
    title: Optional[str] = None,
    hole: float = 0.45,
) -> go.Figure:
    """Generate an executive donut/pie chart."""
    display_title = title or f"Distribution of {values_col.replace('_', ' ').title()} by {names_col.replace('_', ' ').title()}"

    fig = px.pie(
        df,
        names=names_col,
        values=values_col,
        title=display_title,
        hole=hole,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(family="sans-serif", size=13),
        title_font=dict(size=18, color="#1E293B"),
    )
    return fig


def create_area_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """Generate an area chart."""
    display_title = title or f"Cumulative {y_col.replace('_', ' ').title()} across {x_col.replace('_', ' ').title()}"
    df_sorted = df.sort_values(by=x_col)

    fig = px.area(
        df_sorted,
        x=x_col,
        y=y_col,
        color=color_col,
        title=display_title,
        color_discrete_sequence=PALETTE,
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(family="sans-serif", size=13),
        title_font=dict(size=18, color="#1E293B"),
    )
    return fig


def create_scatter_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    size_col: Optional[str] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """Generate a correlation scatter plot."""
    display_title = title or f"{y_col.replace('_', ' ').title()} vs {x_col.replace('_', ' ').title()}"

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        color=color_col,
        size=size_col,
        title=display_title,
        color_discrete_sequence=PALETTE,
        hover_data=df.columns.tolist(),
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(family="sans-serif", size=13),
        title_font=dict(size=18, color="#1E293B"),
    )
    return fig


def auto_generate_chart(df: pd.DataFrame, question: str = "") -> Tuple[Optional[go.Figure], str]:
    """
    Intelligently inspect DataFrame shape and types, select optimal chart,
    and return (figure, chart_type_label).
    """
    if df is None or df.empty:
        return None, "No data available to plot."

    # Single scalar metric (1 row, 1 column)
    if df.shape == (1, 1) and pd.api.types.is_numeric_dtype(df.iloc[:, 0]):
        return create_metric_card(df), "Metric KPI Card"

    classified = _classify_columns(df)
    date_cols = classified["date"]
    cat_cols = classified["categorical"]
    num_cols = classified["numeric"]

    question_lower = question.lower()

    # Case 1: Time Series (Date + Numeric)
    if date_cols and num_cols:
        date_col = date_cols[0]
        num_col = num_cols[0]
        color_col = cat_cols[0] if cat_cols else None
        
        # If user asked for "distribution" or "bar", use bar; otherwise line
        if "bar" in question_lower:
            return create_bar_chart(df, date_col, num_col, color_col=color_col), f"Bar Chart ({num_col} over {date_col})"
        return create_line_chart(df, date_col, num_col, color_col=color_col), f"Time Series Line Chart ({num_col} over {date_col})"

    # Case 2: Categorical + Numeric
    if cat_cols and num_cols:
        cat_col = cat_cols[0]
        num_col = num_cols[0]
        color_col = cat_cols[1] if len(cat_cols) > 1 else None

        num_categories = df[cat_col].nunique()

        # If user asked for pie/share/percentage and <= 7 categories
        if ("share" in question_lower or "percentage" in question_lower or "proportion" in question_lower or "pie" in question_lower) and num_categories <= 7:
            return create_pie_chart(df, cat_col, num_col), f"Donut Chart ({num_col} by {cat_col})"

        # If there are lots of categories, horizontal bar is much cleaner
        if num_categories > 8:
            return create_bar_chart(df, cat_col, num_col, color_col=color_col, horizontal=True), f"Horizontal Bar Chart ({num_col} by {cat_col})"

        return create_bar_chart(df, cat_col, num_col, color_col=color_col), f"Bar Chart ({num_col} by {cat_col})"

    # Case 3: Two Numeric columns
    if len(num_cols) >= 2:
        return create_scatter_chart(df, num_cols[0], num_cols[1]), f"Scatter Plot ({num_cols[1]} vs {num_cols[0]})"

    # Case 4: Single categorical column with counts
    if cat_cols and not num_cols:
        value_counts_df = df[cat_cols[0]].value_counts().reset_index()
        value_counts_df.columns = [cat_cols[0], "count"]
        return create_bar_chart(value_counts_df, cat_cols[0], "count"), f"Bar Chart (Distribution of {cat_cols[0]})"

    return None, "Data columns are not suitable for automatic charting."
