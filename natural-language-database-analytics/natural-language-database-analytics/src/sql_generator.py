"""
SQL Generation Module for Natural Language Database Analytics Agent.

Converts natural language user questions into safe, optimized SQLite queries using
LLM APIs (Google Gemini via google-genai or OpenAI via openai) with structured prompts
and schema injection. Also provides automated natural language insights from query results.
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any
import pandas as pd


SYSTEM_PROMPT_TEMPLATE = """You are an expert Data Analyst and SQLite specialist.
Your task is to convert the user's plain English question into a valid, safe, and efficient SQLite SQL query.

=== DATABASE SCHEMA ===
{schema_ddl}

=== RULES & CONSTRAINTS ===
1. Generate ONLY read-only queries (SELECT or WITH ... SELECT).
2. NEVER use modifying commands: NO INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or PRAGMA.
3. Use SQLite compatible syntax:
   - Dates are stored as 'YYYY-MM-DD' TEXT.
   - For monthly grouping use: strftime('%Y-%m', order_date)
   - For yearly grouping use: strftime('%Y', order_date)
   - For rounding use: ROUND(value, 2)
   - For handling NULLs use: COALESCE(col, default)
4. Use meaningful column aliases (e.g., AS total_revenue, AS order_count).
5. For sales/revenue calculations, use `order_items.total_price` or `(order_items.quantity * order_items.unit_price * (1 - order_items.discount))`.
6. For profit calculations, use `(order_items.unit_price * (1 - order_items.discount) - products.cost_price) * order_items.quantity`.
7. Join tables carefully using the specified foreign keys.
8. Output ONLY the raw SQL query, optionally wrapped in ```sql ... ``` markdown fences. Do not include conversational filler.
"""

INSIGHT_PROMPT_TEMPLATE = """You are an executive business analyst.
The user asked: "{question}"
The following SQL was executed:
```sql
{sql}
```
Here is a summary of the resulting dataset:
{data_summary}

Provide a concise, 2 to 4 bullet-point executive summary answering the user's question directly.
Highlight top performers, trends, key anomalies, or business recommendations. Keep it direct and professional.
"""


def _generate_with_gemini(prompt: str, system_instruction: str, api_key: str, model_name: str) -> str:
    """Generate text using Google Gemini API (google-genai SDK)."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name or "gemini-2.5-flash",
            contents=prompt,
            config={"system_instruction": system_instruction, "temperature": 0.1},
        )
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API Error: {str(e)}")


def _generate_with_openai(prompt: str, system_instruction: str, api_key: str, model_name: str) -> str:
    """Generate text using OpenAI API (openai SDK)."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI API Error: {str(e)}")


def generate_sql(
    question: str,
    schema_ddl: str,
    provider: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate an SQLite query from a natural language question and database schema.
    """
    key = api_key or os.getenv("GEMINI_API_KEY" if provider.lower() == "gemini" else "OPENAI_API_KEY")
    if not key or key.strip() == "" or "your_" in key.lower():
        raise ValueError(
            f"No valid API key found for provider '{provider}'. "
            f"Please configure your {provider.upper()}_API_KEY in the sidebar or in the .env file."
        )

    system_instruction = SYSTEM_PROMPT_TEMPLATE.format(schema_ddl=schema_ddl)
    user_prompt = f"Convert this question into an SQLite SELECT query:\nQuestion: {question}"

    provider_clean = provider.strip().lower()
    if provider_clean == "gemini":
        model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        return _generate_with_gemini(user_prompt, system_instruction, key, model_name)
    elif provider_clean == "openai":
        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return _generate_with_openai(user_prompt, system_instruction, key, model_name)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Choose 'gemini' or 'openai'.")


def generate_summary(
    question: str,
    sql_query: str,
    df: pd.DataFrame,
    provider: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate natural language insights summarizing the SQL query results.
    Falls back to statistical summary if API key is not available.
    """
    if df is None or df.empty:
        return "The query returned 0 records. There is no data to summarize."

    # Format sample or statistical representation of the dataframe
    if len(df) <= 15:
        data_summary = df.to_markdown(index=False)
    else:
        sample_str = df.head(10).to_markdown(index=False)
        describe_str = df.describe().to_markdown()
        data_summary = f"First 10 rows:\n{sample_str}\n\nStatistical summary:\n{describe_str}\nTotal rows: {len(df)}"

    key = api_key or os.getenv("GEMINI_API_KEY" if provider.lower() == "gemini" else "OPENAI_API_KEY")
    if not key or key.strip() == "" or "your_" in key.lower():
        # Fallback to local heuristic summary
        return _fallback_summary(question, df)

    prompt = INSIGHT_PROMPT_TEMPLATE.format(question=question, sql=sql_query, data_summary=data_summary)
    system_instruction = "You are a senior data analyst providing crisp executive highlights."

    try:
        provider_clean = provider.strip().lower()
        if provider_clean == "gemini":
            model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            return _generate_with_gemini(prompt, system_instruction, key, model_name)
        elif provider_clean == "openai":
            model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return _generate_with_openai(prompt, system_instruction, key, model_name)
        else:
            return _fallback_summary(question, df)
    except Exception:
        return _fallback_summary(question, df)


def _fallback_summary(question: str, df: pd.DataFrame) -> str:
    """Heuristic summary generated without an active LLM call."""
    num_rows = len(df)
    cols = list(df.columns)
    lines = [
        f"• **Record Count**: The query returned {num_rows:,} record{'s' if num_rows != 1 else ''} across {len(cols)} attribute(s).",
    ]

    # Look for top numeric column
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and not c.lower().endswith("_id")]
    if numeric_cols:
        primary_metric = numeric_cols[0]
        total_sum = df[primary_metric].sum()
        avg_val = df[primary_metric].mean()
        max_row = df.loc[df[primary_metric].idxmax()]
        label_cols = [c for c in cols if c != primary_metric and not c.lower().endswith("_id")]

        if label_cols:
            top_label = max_row[label_cols[0]]
            lines.append(f"• **Top Performer**: '{top_label}' leads in `{primary_metric}` with a value of {max_row[primary_metric]:,.2f}.")

        lines.append(f"• **Aggregate Metrics**: Total `{primary_metric}` is {total_sum:,.2f} (Average: {avg_val:,.2f}).")

    return "\n".join(lines)
