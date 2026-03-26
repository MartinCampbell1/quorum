"""User-facing scenario presets built on top of raw orchestration modes."""

from orchestrator.models import AgentConfig


SCENARIOS = {
    "repo_audit": {
        "id": "repo_audit",
        "name": "Repo Audit",
        "mode": "dictator",
        "headline": "Координатор ведёт ревью кода, гипотез и рисков.",
        "description": "Подходит для поиска багов, регрессий, слабых мест и архитектурных рисков в локальном проекте.",
        "recommended_for": "Ревью соседнего репозитория, поиск причин багов, подготовка плана фиксов.",
        "task_placeholder": "Например: найди слабые места в нашем trading backend и приоритизируй риски.",
        "tags": ["code", "audit", "bugs"],
        "default_config": {"max_iterations": 3},
        "default_agents": [
            AgentConfig(role="lead_reviewer", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="runtime_investigator", provider="codex", tools=["code_exec", "shell_exec", "web_search"]),
            AgentConfig(role="evidence_analyst", provider="gemini", tools=["web_search", "http_request", "perplexity"]),
        ],
    },
    "pattern_mining": {
        "id": "pattern_mining",
        "name": "Pattern Mining",
        "mode": "map_reduce",
        "headline": "Разбивает данные на куски, ищет закономерности и собирает выводы.",
        "description": "Полезно для анализа торговых логов, сделок, прибыльности, аномалий и повторяющихся паттернов.",
        "recommended_for": "История сделок, PnL, подозрительные повторяющиеся движения, бэктестовые журналы.",
        "task_placeholder": "Например: найди прибыльные и убыточные паттерны в старых сделках по BTC.",
        "tags": ["data", "patterns", "trading"],
        "default_config": {},
        "default_agents": [
            AgentConfig(role="planner", provider="claude", tools=["perplexity", "web_search"]),
            AgentConfig(role="pattern_worker_1", provider="codex", tools=["code_exec", "shell_exec"]),
            AgentConfig(role="pattern_worker_2", provider="gemini", tools=["code_exec", "http_request", "web_search"]),
            AgentConfig(role="synthesizer", provider="claude", tools=["perplexity"]),
        ],
    },
    "news_context": {
        "id": "news_context",
        "name": "News + Context",
        "mode": "board",
        "headline": "Несколько аналитиков сверяют новости, контекст и итоговый взгляд.",
        "description": "Сценарий для быстрого multi-agent ресёрча по рынку, новостям, ончейн-сигналам и внешнему контексту.",
        "recommended_for": "Новости по BTC, реакция рынка, проверка нескольких интерпретаций одной новости.",
        "task_placeholder": "Например: соберите свежие новости по Bitcoin и объясните, что это значит для нашего проекта.",
        "tags": ["news", "research", "market"],
        "default_config": {"max_rounds": 3},
        "default_agents": [
            AgentConfig(role="macro_reader", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="market_reader", provider="gemini", tools=["web_search", "perplexity", "http_request"]),
            AgentConfig(role="skeptic", provider="codex", tools=["web_search", "code_exec"]),
        ],
    },
    "strategy_review": {
        "id": "strategy_review",
        "name": "Strategy Review",
        "mode": "creator_critic",
        "headline": "Один агент предлагает стратегию, второй давит на риски и улучшения.",
        "description": "Хорошо работает для личного мозгового штурма, проверки гипотез и жёсткой критики планов.",
        "recommended_for": "Торговые стратегии, product decisions, системный разбор идеи перед внедрением.",
        "task_placeholder": "Например: предложи улучшение нашей стратегии входа и затем жёстко раскритикуй её.",
        "tags": ["strategy", "review", "ideas"],
        "default_config": {"max_iterations": 3},
        "default_agents": [
            AgentConfig(role="strategist", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="risk_critic", provider="codex", tools=["code_exec", "web_search", "shell_exec"]),
        ],
    },
}


def get_scenario(scenario_id: str):
    return SCENARIOS.get(scenario_id)


def list_scenarios() -> list[dict]:
    payload: list[dict] = []
    for scenario in SCENARIOS.values():
        payload.append(
            {
                **{k: v for k, v in scenario.items() if k != "default_agents"},
                "default_agents": [agent.model_dump() for agent in scenario["default_agents"]],
            }
        )
    return payload
