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
    "portfolio_pivot_lab": {
        "id": "portfolio_pivot_lab",
        "name": "Portfolio Pivot Lab",
        "mode": "board",
        "headline": "Совет агентов перерабатывает текущие проекты в более сильные pivot-варианты под founder fit.",
        "description": "Подходит для работы с портфелем локальных проектов: найти по 2-3 сильных пивота на каждый, отсеять слабые направления и собрать shortlist для турнира или Autopilot.",
        "recommended_for": "Когда есть несколько интересных репозиториев и нужно не просто выбрать победителя, а пересобрать их в более сильные бизнес-направления.",
        "task_placeholder": "Например: возьмите мои AI, crypto и automation проекты, предложите по 2-3 сильных pivot-версии для каждого, затем соберите shortlist с founder-fit, time-to-money и тем, что стоит отправить в турнир или сразу в Autopilot.",
        "tags": ["founderos", "portfolio", "pivots"],
        "default_config": {"max_rounds": 3},
        "default_agents": [
            AgentConfig(role="portfolio_strategist", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="market_scout", provider="gemini", tools=["web_search", "perplexity", "http_request"]),
            AgentConfig(role="pivot_critic", provider="codex", tools=["web_search", "code_exec", "shell_exec"]),
        ],
    },
    "consensus_vote": {
        "id": "consensus_vote",
        "name": "Consensus Vote",
        "mode": "democracy",
        "headline": "Несколько голосующих агентов независимо оценивают варианты и собирают majority verdict.",
        "description": "Подходит для продуктовых решений, сравнений вариантов, быстрых go/no-go развилок и проверки, где реально есть большинство.",
        "recommended_for": "Ship / no-ship, выбор приоритета, сравнение гипотез, быстрый majority-based decision.",
        "task_placeholder": "Например: стоит ли выкатывать новую onboarding-цепочку на всех пользователей на этой неделе?",
        "tags": ["decision", "vote", "consensus"],
        "default_config": {"max_rounds": 3},
        "default_agents": [
            AgentConfig(role="voter_1", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="voter_2", provider="gemini", tools=["web_search", "perplexity", "http_request"]),
            AgentConfig(role="voter_3", provider="codex", tools=["web_search", "code_exec"]),
        ],
    },
    "structured_debate": {
        "id": "structured_debate",
        "name": "Structured Debate",
        "mode": "debate",
        "headline": "Две стороны спорят по существу, а судья фиксирует итоговый вердикт.",
        "description": "Полезно для проверки спорных технических решений, product trade-offs и выбора между двумя взаимоисключающими курсами.",
        "recommended_for": "Архитектурные споры, buy vs build, rewrite vs incremental refactor, speed vs safety.",
        "task_placeholder": "Например: нужно ли нам переписывать orchestration shell сейчас или лучше идти инкрементально?",
        "tags": ["debate", "tradeoffs", "verdict"],
        "default_config": {"max_rounds": 3},
        "default_agents": [
            AgentConfig(role="proponent", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="opponent", provider="codex", tools=["web_search", "code_exec", "shell_exec"]),
            AgentConfig(role="judge", provider="gemini", tools=["web_search", "http_request", "perplexity"]),
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
    "project_tournament": {
        "id": "project_tournament",
        "name": "Project Tournament",
        "mode": "tournament",
        "headline": "Несколько проектов проходят через head-to-head дебаты по турнирной сетке, а судья выбирает чемпиона.",
        "description": "Подходит для отбора лучшей идеи или репозитория среди нескольких локальных проектов через серию очных матчей с аргументами и вердиктом судьи.",
        "recommended_for": "Сравнение нескольких pet-проектов, репозиториев, MVP-идей или направлений развития по одной задаче.",
        "task_placeholder": "Например: выберите, какой проект соло-фаундеру стоит развивать первым, чтобы быстрее выйти к стабильным $2K+/мес, а в финале назовите победителя, второе место и что заморозить.",
        "tags": ["tournament", "projects", "comparison"],
        "default_config": {"max_rounds": 5},
        "default_agents": [
            AgentConfig(role="contestant_1", provider="claude", tools=["web_search", "code_exec", "shell_exec"]),
            AgentConfig(role="contestant_2", provider="codex", tools=["code_exec", "shell_exec", "web_search"]),
            AgentConfig(role="contestant_3", provider="gemini", tools=["web_search", "http_request", "perplexity"]),
            AgentConfig(role="contestant_4", provider="claude", tools=["web_search", "perplexity"]),
            AgentConfig(role="judge", provider="gemini", tools=["web_search", "perplexity", "http_request"]),
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
