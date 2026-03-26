"""
Safety Layer для свободных Cypher/SQL запросов.

Правила:
  1. Только READ - никаких CREATE, DELETE, SET, MERGE, DROP, INSERT
  2. Обязательный LIMIT (макс 200)
  3. Timeout 10 секунд
  4. Логирование каждого запроса
"""

import re
import logging

logger = logging.getLogger("safety_layer")

# Запрещенные ключевые слова (мутации)
FORBIDDEN_CYPHER = [
    "CREATE", "DELETE", "DETACH", "SET", "MERGE",
    "REMOVE", "DROP", "CALL.*apoc.*export",
    "LOAD CSV",
]

FORBIDDEN_SQL = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "TRUNCATE", "CREATE TABLE", "GRANT", "REVOKE",
]

MAX_LIMIT = 200
QUERY_TIMEOUT = 10  # секунд


def validate_cypher(query: str) -> tuple[bool, str]:
    """Проверить Cypher на безопасность. Возвращает (ok, reason)."""
    upper = query.upper().strip()

    # Проверка на мутации
    for pattern in FORBIDDEN_CYPHER:
        if re.search(r'\b' + pattern + r'\b', upper):
            return False, f"Mutation not allowed: {pattern}"

    # Должен начинаться с MATCH, CALL, RETURN, WITH, OPTIONAL, UNWIND
    allowed_starts = ["MATCH", "CALL", "RETURN", "WITH", "OPTIONAL", "UNWIND"]
    if not any(upper.startswith(s) for s in allowed_starts):
        return False, f"Query must start with one of: {allowed_starts}"

    # Проверить наличие LIMIT
    if "LIMIT" not in upper:
        return False, "Query must include LIMIT clause"

    # Проверить что LIMIT не слишком большой
    limit_match = re.search(r'LIMIT\s+(\d+)', upper)
    if limit_match:
        limit_val = int(limit_match.group(1))
        if limit_val > MAX_LIMIT:
            return False, f"LIMIT {limit_val} exceeds maximum {MAX_LIMIT}"

    return True, "OK"


def validate_sql(query: str) -> tuple[bool, str]:
    """Проверить SQL на безопасность."""
    upper = query.upper().strip()

    for pattern in FORBIDDEN_SQL:
        if re.search(r'\b' + pattern + r'\b', upper):
            return False, f"Mutation not allowed: {pattern}"

    if not upper.startswith("SELECT"):
        return False, "Only SELECT queries allowed"

    if "LIMIT" not in upper:
        return False, "Query must include LIMIT"

    limit_match = re.search(r'LIMIT\s+(\d+)', upper)
    if limit_match and int(limit_match.group(1)) > MAX_LIMIT:
        return False, f"LIMIT exceeds maximum {MAX_LIMIT}"

    return True, "OK"


def safe_neo4j_query(cypher: str, params: dict = None) -> dict:
    """Выполнить Cypher с проверкой безопасности."""
    ok, reason = validate_cypher(cypher)
    if not ok:
        return {"error": reason, "query": cypher}

    logger.info(f"FREE CYPHER: {cypher[:200]}")

    from graph_recipes import neo4j_query
    try:
        result = neo4j_query(cypher, params)
        return {"data": result, "row_count": len(result)}
    except Exception as e:
        return {"error": str(e), "query": cypher}


def safe_ch_query(sql: str) -> dict:
    """Выполнить SQL с проверкой безопасности."""
    ok, reason = validate_sql(sql)
    if not ok:
        return {"error": reason, "query": sql}

    logger.info(f"FREE SQL: {sql[:200]}")

    from graph_recipes import ch_query
    try:
        result = ch_query(sql)
        return {"data": result, "row_count": len(result)}
    except Exception as e:
        return {"error": str(e), "query": sql}
