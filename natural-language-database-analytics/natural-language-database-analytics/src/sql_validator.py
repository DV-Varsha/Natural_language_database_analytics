"""
SQL Security and Validation Module.

Enforces strict read-only execution by validating that:
1. Only a single SQL statement is provided (preventing statement stacking / injections).
2. The query is an Abstract Syntax Tree (AST) recognized SELECT or UNION query (or WITH CTE).
3. Modifying operations (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.) are strictly rejected.
4. Dangerous administrative commands or SQLite functions (PRAGMA, ATTACH, DETACH, load_extension, etc.) are blocked.
"""

from __future__ import annotations

import re
from typing import Tuple, Optional

try:
    import sqlglot
    from sqlglot import exp
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False


DISALLOWED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "REPLACE", "MERGE", "UPSERT", "PRAGMA", "ATTACH", "DETACH", "VACUUM",
    "REINDEX", "EXEC", "EXECUTE", "GRANT", "REVOKE", "INTO"
}

DISALLOWED_FUNCTIONS = {
    "LOAD_EXTENSION", "READFILE", "WRITEFILE", "EDIT"
}


def sanitize_sql(raw_sql: str) -> str:
    """
    Remove Markdown code fences, comments, and redundant leading/trailing whitespace.
    """
    cleaned = raw_sql.strip()

    # Match ```sql ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if code_block_match:
        cleaned = code_block_match.group(1).strip()

    # Remove single line comments starting with --
    cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)
    
    # Remove block comments /* ... */
    cleaned = re.sub(r"/\*[\s\S]*?\*/", "", cleaned)

    cleaned = cleaned.strip()
    # Strip trailing semicolons
    cleaned = cleaned.rstrip(";")
    return cleaned.strip()


def _validate_with_sqlglot(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SQL safety using sqlglot AST parsing.
    """
    try:
        parsed_expressions = sqlglot.parse(sql, read="sqlite")
    except Exception as e:
        return False, f"SQL syntax error or unparseable query: {str(e)}"

    if not parsed_expressions:
        return False, "Query is empty."

    if len(parsed_expressions) > 1:
        return False, "Multiple SQL statements detected. Only a single read-only query is permitted."

    expression = parsed_expressions[0]
    if expression is None:
        return False, "Empty SQL expression."

    # Top-level expression must be a SELECT, a UNION of SELECTs, or a CTE (WITH ... SELECT)
    is_valid_root = False
    if isinstance(expression, (exp.Select, exp.Union)):
        is_valid_root = True
    elif isinstance(expression, exp.Expression):
        # Check if it's a CTE (WITH clause) ending in a SELECT or UNION
        if expression.key.lower() in ("select", "union"):
            is_valid_root = True
        elif hasattr(expression, "this") and isinstance(expression.this, (exp.Select, exp.Union)):
            is_valid_root = True

    if not is_valid_root:
        return False, f"Prohibited root statement type: '{expression.key.upper()}'. Only SELECT queries are permitted."

    # Inspect all nodes in the AST for disallowed operations
    prohibited_ast_types = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop,
        exp.Alter, exp.Create, exp.Command, exp.Pragma,
        exp.Merge
    )

    for node in expression.walk():
        if isinstance(node, prohibited_ast_types):
            node_name = node.__class__.__name__.replace("Table", "").upper()
            return False, f"Prohibited modification operation detected in query: '{node_name}'."

        # Check for disallowed function calls
        if isinstance(node, exp.Anonymous):
            func_name = node.name.upper()
            if func_name in DISALLOWED_FUNCTIONS:
                return False, f"Dangerous SQLite function execution blocked: '{func_name}'."

    return True, None


def _validate_with_heuristics(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Fallback heuristic validator if sqlglot is not yet installed or active.
    """
    upper_sql = sql.upper().strip()

    # Reject semicolon inside statements
    statements = [s.strip() for s in upper_sql.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements detected. Only a single query is permitted."

    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        return False, "Only read-only SELECT or WITH statements are allowed."

    # Check for disallowed keywords as distinct words
    for kw in DISALLOWED_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", upper_sql):
            # Special exemption: INTO is prohibited unless in SELECT ... INTO which we also forbid
            return False, f"Prohibited keyword detected: '{kw}'. Modifications are not permitted."

    for func in DISALLOWED_FUNCTIONS:
        if re.search(r"\b" + re.escape(func) + r"\b", upper_sql):
            return False, f"Dangerous function detected: '{func}'."

    return True, None


def validate_sql(raw_sql: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validate a raw SQL string from the user or LLM.

    Returns:
        (is_valid: bool, sanitized_sql: str, error_message: str | None)
    """
    sanitized = sanitize_sql(raw_sql)
    if not sanitized:
        return False, "", "The generated SQL query is empty."

    if SQLGLOT_AVAILABLE:
        valid, err = _validate_with_sqlglot(sanitized)
        if not valid:
            return False, sanitized, err
    else:
        valid, err = _validate_with_heuristics(sanitized)
        if not valid:
            return False, sanitized, err

    return True, sanitized, None
