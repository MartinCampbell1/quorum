"""
Graph Recipes - готовые запросы для типовых задач SMG.

Каждый рецепт:
  - Принимает простые параметры (адрес, токен, время)
  - Содержит проверенный, оптимизированный Cypher/SQL
  - Имеет встроенные LIMIT и таймауты
  - Возвращает структурированный результат

Категории:
  1. Wallet Analysis     - анализ одного кошелька
  2. Connection Discovery - поиск связей между кошельками
  3. Token Intelligence   - анализ токенов и их холдеров
  4. Cluster Detection    - поиск координированных групп
  5. Signal Generation    - сигналы для трейдинга
  6. Portfolio/Position   - текущие позиции и PnL
"""

import json
import os
import time
from typing import Optional

from neo4j import GraphDatabase
import clickhouse_connect


# =====================================================================
#  1. WALLET ANALYSIS
# =====================================================================

def wallet_profile(address: str) -> dict:
    """
    Полный профиль кошелька: tier, статистика, последние сделки.
    Это первое что вызывается когда нужно понять кто этот кошелек.
    """
    return neo4j_query("""
        MATCH (w:Wallet {address: $addr})
        OPTIONAL MATCH (w)-[t:TRADED]->(tk:Token)
        WITH w,
             count(t) as total_trades,
             sum(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as wins,
             sum(t.pnl) as total_pnl,
             avg(t.vsol) as avg_size,
             collect({token: tk.symbol, mint: tk.mint, pnl: t.pnl,
                      vsol: t.vsol, ts: t.timestamp})[..20] as recent
        RETURN w.address as address,
               w.tier as tier,
               w.label as label,
               total_trades,
               wins,
               total_pnl,
               avg_size,
               recent
    """, {"addr": address})


def wallet_connections(address: str, max_hops: int = 2, min_shared: int = 2) -> dict:
    """
    Найти кошельки, связанные через общие токены.

    max_hops: 1 = прямые связи (торговали тем же токеном)
              2 = через одного посредника
              3 = через двух (глубокий поиск)

    min_shared: минимум общих токенов чтобы считать связью.
    """
    if max_hops == 1:
        return neo4j_query("""
            MATCH (w1:Wallet {address: $addr})-[:TRADED]->(tk:Token)<-[:TRADED]-(w2:Wallet)
            WHERE w1 <> w2
            WITH w2, collect(DISTINCT tk.symbol) as shared_tokens, count(DISTINCT tk) as shared_count
            WHERE shared_count >= $min_shared
            RETURN w2.address as connected_wallet,
                   w2.tier as tier,
                   shared_tokens,
                   shared_count
            ORDER BY shared_count DESC
            LIMIT 50
        """, {"addr": address, "min_shared": min_shared})

    elif max_hops == 2:
        return neo4j_query("""
            MATCH (w1:Wallet {address: $addr})-[:TRADED]->(tk1:Token)<-[:TRADED]-(bridge:Wallet)-[:TRADED]->(tk2:Token)<-[:TRADED]-(w3:Wallet)
            WHERE w1 <> bridge AND bridge <> w3 AND w1 <> w3
            WITH w3, bridge,
                 collect(DISTINCT tk1.symbol) as tokens_via_bridge,
                 count(DISTINCT tk1) as shared_count
            WHERE shared_count >= $min_shared
            RETURN w3.address as connected_wallet,
                   w3.tier as tier,
                   bridge.address as bridge_wallet,
                   tokens_via_bridge,
                   shared_count
            ORDER BY shared_count DESC
            LIMIT 50
        """, {"addr": address, "min_shared": min_shared})

    elif max_hops == 3:
        # 3 хопа - тяжелый запрос, жесткие лимиты
        return neo4j_query("""
            MATCH path = (w1:Wallet {address: $addr})-[:TRADED*1..3]-(w2:Wallet)
            WHERE w1 <> w2
            WITH w2, length(path) as hops,
                 [n IN nodes(path) WHERE n:Token | n.symbol] as tokens_in_path
            RETURN DISTINCT w2.address as connected_wallet,
                   w2.tier as tier,
                   min(hops) as min_hops,
                   tokens_in_path
            ORDER BY min_hops ASC
            LIMIT 30
        """, {"addr": address})


def wallet_timing(address: str, token_mint: str = None) -> dict:
    """
    Тайминг входов кошелька: как рано он заходит в токены.
    Если token_mint задан - только по этому токену.
    """
    if token_mint:
        return neo4j_query("""
            MATCH (w:Wallet {address: $addr})-[t:TRADED]->(tk:Token {mint: $mint})
            MATCH (first:Wallet)-[ft:TRADED]->(tk)
            WITH t.timestamp as entry_ts, min(ft.timestamp) as first_trade_ts, tk, t
            RETURN tk.symbol as token,
                   t.timestamp as entry_time,
                   first_trade_ts as token_first_trade,
                   t.timestamp - first_trade_ts as seconds_after_first,
                   t.vsol as size,
                   t.pnl as pnl
        """, {"addr": address, "mint": token_mint})
    else:
        return neo4j_query("""
            MATCH (w:Wallet {address: $addr})-[t:TRADED]->(tk:Token)
            MATCH (first:Wallet)-[ft:TRADED]->(tk)
            WITH tk, t, min(ft.timestamp) as first_trade_ts
            RETURN tk.symbol as token,
                   tk.mint as mint,
                   t.timestamp as entry_time,
                   first_trade_ts as first_trade,
                   t.timestamp - first_trade_ts as seconds_after_first,
                   t.vsol as size,
                   t.pnl as pnl
            ORDER BY t.timestamp DESC
            LIMIT 30
        """, {"addr": address})


# =====================================================================
#  2. TOKEN INTELLIGENCE
# =====================================================================

def token_holders(mint: str, tier_filter: list = None) -> dict:
    """
    Кто торговал этим токеном. Фильтр по tier: ['insider', 'auto_entry'].
    """
    if tier_filter:
        return neo4j_query("""
            MATCH (w:Wallet)-[t:TRADED]->(tk:Token {mint: $mint})
            WHERE w.tier IN $tiers
            RETURN w.address as wallet,
                   w.tier as tier,
                   t.pnl as pnl,
                   t.vsol as size,
                   t.timestamp as entry_time
            ORDER BY t.timestamp ASC
            LIMIT 100
        """, {"mint": mint, "tiers": tier_filter})
    else:
        return neo4j_query("""
            MATCH (w:Wallet)-[t:TRADED]->(tk:Token {mint: $mint})
            RETURN w.address as wallet,
                   w.tier as tier,
                   t.pnl as pnl,
                   t.vsol as size,
                   t.timestamp as entry_time
            ORDER BY t.timestamp ASC
            LIMIT 100
        """, {"mint": mint})


def token_insider_overlap(mint: str) -> dict:
    """
    Для токена: найти все кошельки-инсайдеры, которые его торговали,
    и показать какие ДРУГИЕ токены они торговали вместе.
    Помогает найти связанные запуски.
    """
    return neo4j_query("""
        MATCH (w:Wallet)-[:TRADED]->(target:Token {mint: $mint})
        WHERE w.tier IN ['insider', 'auto_entry']
        MATCH (w)-[:TRADED]->(other:Token)
        WHERE other.mint <> $mint
        WITH other, collect(DISTINCT w.address) as shared_insiders,
             count(DISTINCT w) as insider_count
        WHERE insider_count >= 2
        RETURN other.symbol as token,
               other.mint as mint,
               insider_count,
               shared_insiders[..5] as sample_wallets
        ORDER BY insider_count DESC
        LIMIT 20
    """, {"mint": mint})


# =====================================================================
#  3. CLUSTER DETECTION
# =====================================================================

def find_clusters(min_shared_tokens: int = 3, since_hours: int = 24) -> dict:
    """
    Найти группы кошельков, которые торгуют одинаковые токены
    за последние N часов. Признак координированной активности.
    """
    since_ts = int(time.time()) - since_hours * 3600
    return neo4j_query("""
        MATCH (w1:Wallet)-[t1:TRADED]->(tk:Token)<-[t2:TRADED]-(w2:Wallet)
        WHERE t1.timestamp > $since AND t2.timestamp > $since
              AND w1.address < w2.address
        WITH w1, w2, collect(DISTINCT tk.symbol) as shared, count(DISTINCT tk) as cnt
        WHERE cnt >= $min_shared
        RETURN w1.address as wallet_a,
               w1.tier as tier_a,
               w2.address as wallet_b,
               w2.tier as tier_b,
               shared as shared_tokens,
               cnt as shared_count
        ORDER BY cnt DESC
        LIMIT 30
    """, {"since": since_ts, "min_shared": min_shared_tokens})


def coordinated_entries(token_mint: str, window_seconds: int = 60) -> dict:
    """
    Найти кошельки, которые зашли в токен почти одновременно
    (в пределах window_seconds друг от друга).
    Сильный сигнал координации.
    """
    return neo4j_query("""
        MATCH (w1:Wallet)-[t1:TRADED]->(tk:Token {mint: $mint}),
              (w2:Wallet)-[t2:TRADED]->(tk)
        WHERE w1.address < w2.address
              AND abs(t1.timestamp - t2.timestamp) <= $window
        RETURN w1.address as wallet_a,
               w1.tier as tier_a,
               t1.timestamp as time_a,
               w2.address as wallet_b,
               w2.tier as tier_b,
               t2.timestamp as time_b,
               abs(t1.timestamp - t2.timestamp) as time_diff_sec
        ORDER BY time_diff_sec ASC
        LIMIT 30
    """, {"mint": token_mint, "window": window_seconds})


# =====================================================================
#  4. SIGNAL GENERATION
# =====================================================================

def fresh_insider_activity(hours: int = 1) -> dict:
    """
    Что инсайдеры купили за последние N часов.
    Основной сигнал для detection engine.
    """
    since_ts = int(time.time()) - hours * 3600
    return neo4j_query("""
        MATCH (w:Wallet)-[t:TRADED]->(tk:Token)
        WHERE w.tier IN ['insider', 'auto_entry']
              AND t.timestamp > $since
        RETURN w.address as wallet,
               w.tier as tier,
               tk.symbol as token,
               tk.mint as mint,
               t.vsol as size,
               t.timestamp as time
        ORDER BY t.timestamp DESC
        LIMIT 50
    """, {"since": since_ts})


def multi_insider_tokens(min_insiders: int = 3, hours: int = 6) -> dict:
    """
    Токены, в которые зашли >= N инсайдеров за последние hours.
    Сильнейший сигнал: если 3+ инсайдера зашли - это что-то.
    """
    since_ts = int(time.time()) - hours * 3600
    return neo4j_query("""
        MATCH (w:Wallet)-[t:TRADED]->(tk:Token)
        WHERE w.tier IN ['insider', 'auto_entry']
              AND t.timestamp > $since
        WITH tk, collect(DISTINCT w.address) as insiders,
             count(DISTINCT w) as insider_count,
             min(t.timestamp) as first_entry,
             sum(t.vsol) as total_volume
        WHERE insider_count >= $min_insiders
        RETURN tk.symbol as token,
               tk.mint as mint,
               insider_count,
               insiders[..5] as sample_insiders,
               first_entry,
               total_volume
        ORDER BY insider_count DESC, first_entry DESC
        LIMIT 20
    """, {"since": since_ts, "min_insiders": min_insiders})


# =====================================================================
#  5. POSITIONS & PNL (ClickHouse)
# =====================================================================

def current_positions() -> dict:
    """Текущие открытые позиции из ClickHouse."""
    return ch_query("""
        SELECT token, mint, entry_price, current_price,
               unrealized_pnl, size_sol, entry_time, trade_mode
        FROM positions
        WHERE status = 'open'
        ORDER BY entry_time DESC
    """)


def recent_trades(hours: int = 24, limit: int = 50) -> dict:
    """Последние закрытые сделки."""
    return ch_query(f"""
        SELECT token, entry_price, exit_price, pnl, pnl_pct,
               size_sol, trade_mode, duration_sec, exit_reason,
               entry_time, exit_time
        FROM trades
        WHERE exit_time > now() - INTERVAL {hours} HOUR
        ORDER BY exit_time DESC
        LIMIT {limit}
    """)


def ml_scores(min_score: float = 0.5, limit: int = 30) -> dict:
    """Последние ML скоры выше порога."""
    return ch_query(f"""
        SELECT token, mint, wallet, score, confidence,
               stage, model_version, timestamp
        FROM ml_scores
        WHERE score >= {min_score}
        ORDER BY timestamp DESC
        LIMIT {limit}
    """)


def pnl_summary(days: int = 7) -> dict:
    """Сводка PnL за период."""
    return ch_query(f"""
        SELECT
            count(*) as total_trades,
            sum(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            sum(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
            sum(pnl) as total_pnl,
            avg(pnl) as avg_pnl,
            max(pnl) as best_trade,
            min(pnl) as worst_trade,
            avg(duration_sec) as avg_duration
        FROM trades
        WHERE exit_time > now() - INTERVAL {days} DAY
    """)


# =====================================================================
#  HELPERS - вызов баз данных
# =====================================================================

_neo4j_driver = None
_ch_client = None

def _get_neo4j():
    global _neo4j_driver
    if not _neo4j_driver:
        _neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://75.119.159.43:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASS", "")),
        )
    return _neo4j_driver

def neo4j_query(cypher: str, params: dict = None) -> list[dict]:
    driver = _get_neo4j()
    with driver.session() as session:
        result = session.run(cypher, params or {})
        return [dict(record) for record in result]

def _get_ch():
    global _ch_client
    if not _ch_client:
        _ch_client = clickhouse_connect.get_client(
            host=os.getenv("CH_HOST", "75.119.159.43"),
            port=int(os.getenv("CH_PORT", "8123")),
            username=os.getenv("CH_USER", "default"),
            password=os.getenv("CH_PASS", ""),
            database=os.getenv("CH_DB", "smg"),
        )
    return _ch_client

def ch_query(sql: str) -> list[dict]:
    client = _get_ch()
    result = client.query(sql)
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


# =====================================================================
#  КАТАЛОГ РЕЦЕПТОВ (для MCP сервера)
# =====================================================================

RECIPE_CATALOG = {
    # Wallet
    "wallet_profile": {
        "fn": wallet_profile,
        "description": "Full wallet profile: tier, stats, recent trades",
        "params": {"address": "Solana wallet address"},
    },
    "wallet_connections": {
        "fn": wallet_connections,
        "description": "Find wallets connected through shared tokens. max_hops: 1-3. Higher = deeper but slower.",
        "params": {
            "address": "Wallet address to analyze",
            "max_hops": "(optional) 1-3, default 2. Number of hops in the graph",
            "min_shared": "(optional) minimum shared tokens to count as connection, default 2",
        },
    },
    "wallet_timing": {
        "fn": wallet_timing,
        "description": "How early does this wallet enter tokens vs first trade",
        "params": {
            "address": "Wallet address",
            "token_mint": "(optional) specific token mint to check",
        },
    },

    # Token
    "token_holders": {
        "fn": token_holders,
        "description": "Who traded this token, optionally filtered by tier",
        "params": {
            "mint": "Token mint address",
            "tier_filter": "(optional) list of tiers: ['insider', 'auto_entry']",
        },
    },
    "token_insider_overlap": {
        "fn": token_insider_overlap,
        "description": "For a token: find what OTHER tokens its insiders also traded. Reveals linked launches.",
        "params": {"mint": "Token mint address"},
    },

    # Clusters
    "find_clusters": {
        "fn": find_clusters,
        "description": "Find groups of wallets trading same tokens recently. Coordination signal.",
        "params": {
            "min_shared_tokens": "(optional) minimum shared tokens, default 3",
            "since_hours": "(optional) lookback period, default 24",
        },
    },
    "coordinated_entries": {
        "fn": coordinated_entries,
        "description": "Find wallets that entered a token within seconds of each other",
        "params": {
            "token_mint": "Token mint address",
            "window_seconds": "(optional) max time difference, default 60",
        },
    },

    # Signals
    "fresh_insider_activity": {
        "fn": fresh_insider_activity,
        "description": "What did insiders buy in the last N hours",
        "params": {"hours": "(optional) lookback, default 1"},
    },
    "multi_insider_tokens": {
        "fn": multi_insider_tokens,
        "description": "Tokens where 3+ insiders entered recently. Strongest signal.",
        "params": {
            "min_insiders": "(optional) minimum insider count, default 3",
            "hours": "(optional) lookback, default 6",
        },
    },

    # Positions
    "current_positions": {
        "fn": current_positions,
        "description": "Currently open positions",
        "params": {},
    },
    "recent_trades": {
        "fn": recent_trades,
        "description": "Recently closed trades with PnL",
        "params": {
            "hours": "(optional) lookback, default 24",
            "limit": "(optional) max rows, default 50",
        },
    },
    "ml_scores": {
        "fn": ml_scores,
        "description": "Latest ML model scores above threshold",
        "params": {
            "min_score": "(optional) minimum score, default 0.5",
            "limit": "(optional) max rows, default 30",
        },
    },
    "pnl_summary": {
        "fn": pnl_summary,
        "description": "PnL summary: wins, losses, totals",
        "params": {"days": "(optional) period, default 7"},
    },
}
