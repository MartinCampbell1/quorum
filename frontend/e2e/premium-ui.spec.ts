import { expect, Page, test } from "@playwright/test";

const scenarios = [
  { id: "repo_audit", name: "Repo Audit", mode: "dictator", headline: "", description: "", recommended_for: "", task_placeholder: "", tags: [], default_config: {}, default_agents: [] },
  { id: "board_review", name: "Board Review", mode: "board", headline: "", description: "", recommended_for: "", task_placeholder: "", tags: [], default_config: {}, default_agents: [] },
  { id: "team_vote", name: "Team Vote", mode: "democracy", headline: "", description: "", recommended_for: "", task_placeholder: "", tags: [], default_config: {}, default_agents: [] },
  { id: "debate_mode", name: "Debate", mode: "debate", headline: "", description: "", recommended_for: "", task_placeholder: "", tags: [], default_config: {}, default_agents: [] },
  { id: "reduce_ops", name: "Reduce Ops", mode: "map_reduce", headline: "", description: "", recommended_for: "", task_placeholder: "", tags: [], default_config: {}, default_agents: [] },
  { id: "draft_review", name: "Draft Review", mode: "creator_critic", headline: "", description: "", recommended_for: "", task_placeholder: "", tags: [], default_config: {}, default_agents: [] },
];

const toolTypes = {
  mcp_server: {
    name: "MCP Server",
    category: "mcp",
    icon: "🔌",
    fields: [
      { name: "transport", label: "Transport", type: "select", required: true, options: ["stdio", "http"] },
      { name: "command", label: "Команда запуска", type: "text", required: false, placeholder: "npx -y @modelcontextprotocol/server-github" },
      { name: "args", label: "Аргументы (через пробел)", type: "text", required: false, placeholder: "" },
      { name: "env", label: "Переменные окружения (JSON)", type: "textarea", required: false, placeholder: "{\"GITHUB_TOKEN\":\"ghp_...\"}" },
      { name: "url", label: "HTTP URL", type: "text", required: false, placeholder: "https://stitch.googleapis.com/mcp" },
      { name: "headers", label: "HTTP headers (JSON)", type: "textarea", required: false, placeholder: "{\"X-Goog-Api-Key\":\"...\"}" },
    ],
  },
  brave_search: {
    name: "Brave Search",
    category: "search",
    icon: "🔍",
    fields: [{ name: "api_key", label: "API Key", type: "password", required: true, placeholder: "BSA-..." }],
  },
};

const promptTemplates = {
  analyst: {
    name: "Аналитик",
    description: "Анализ данных",
    prompt: "Ты аналитик данных.",
  },
};

const workspacePresets = [
  {
    id: "trading_stack",
    name: "Trading Stack",
    description: "Repo + logs + docs",
    paths: ["/Users/example/Desktop/solana-smart-money-graph", "/Users/example/trading/logs"],
    created_at: 1_700_000_000,
  },
];

const configuredTools = [
  {
    id: "stitch_mcp",
    name: "Stitch MCP",
    tool_type: "mcp_server",
    icon: "🔌",
    enabled: true,
    transport: "http",
    config: {
      transport: "http",
      url: "https://stitch.googleapis.com/mcp",
      headers: "{\"X-Goog-Api-Key\": \"token\"}",
    },
    compatibility: {
      claude: "native",
      gemini: "native",
      codex: "bridged",
      minimax: "unavailable",
    },
    validation_status: "valid",
    last_validation_result: {
      ok: true,
      transport: "http",
      tool_count: 4,
      log: [
        "> Resolving remote endpoint...",
        "> Sending capabilities request...",
        "> Waiting for HTTP handshake...",
        "> Connection successful. Remote MCP ready.",
      ],
    },
  },
];

const providerCapabilities = {
  providers: ["claude", "gemini", "codex", "minimax"],
  tools: {
    web_search: { claude: "native", gemini: "native", codex: "native", minimax: "unavailable" },
    stitch_mcp: { claude: "native", gemini: "native", codex: "bridged", minimax: "unavailable" },
  },
};

const sessionSummary = [
  {
    id: "sess_alpha",
    mode: "board",
    task: "Project Alpha",
    status: "running",
    created_at: Math.floor(Date.now() / 1000) - 7200,
    active_scenario: "board_review",
    forked_from: null,
  },
];

const sessionDetail = {
  id: "sess_alpha",
  mode: "board",
  task: "Project Alpha",
  agents: [
    { role: "orchestrator", provider: "gemini", system_prompt: "", tools: ["optimization_mcp"] },
    { role: "researcher", provider: "claude", system_prompt: "", tools: ["local_filesystem", "postgresql"] },
    { role: "writer", provider: "codex", system_prompt: "", tools: ["web_search"] },
  ],
  messages: [
    { agent_id: "researcher", content: "Local filesystem scanned and draft located.", timestamp: 1_700_000_010, phase: "board_round_1" },
    { agent_id: "writer", content: "Synthesis draft prepared with latest market context.", timestamp: 1_700_000_020, phase: "worker_execution" },
  ],
  result: "Board decision: ship Project Alpha with filesystem and PostgreSQL evidence.",
  status: "running",
  config: {},
  active_scenario: "board_review",
  forked_from: null,
  forked_checkpoint_id: null,
  capabilities: { live_messages: true, custom_tools: true, pause_resume: true, checkpoints: true, workspace_presets: true, branching: true },
  created_at: 1_700_000_000,
  elapsed_sec: 245,
  current_checkpoint_id: "cp_3",
  checkpoints: [
    { id: "cp_1", timestamp: 1_700_000_005, next_node: "check_consensus", status: "ready", result_preview: "" },
    { id: "cp_2", timestamp: 1_700_000_015, next_node: "delegate_to_workers", status: "ready", result_preview: "" },
    { id: "cp_3", timestamp: 1_700_000_025, next_node: "finalize", status: "ready", result_preview: "Board decision in progress" },
  ],
  events: [
    { id: 1, timestamp: 1_700_000_001, type: "run_started", title: "Сессия запущена", detail: "Project Alpha", status: "running", mode: "board" },
    { id: 2, timestamp: 1_700_000_006, type: "vote_recorded", title: "Позиция директора", detail: "Prioritize local evidence", agent_id: "researcher" },
    { id: 3, timestamp: 1_700_000_016, type: "round_completed", title: "Board round 1 завершён", detail: "Consensus reached around Project Alpha" },
    { id: 4, timestamp: 1_700_000_026, type: "checkpoint_created", title: "Checkpoint cp_3", detail: "Следующий узел: finalize", checkpoint_id: "cp_3", next_node: "finalize", status: "ready" },
  ],
  pending_instructions: 0,
  active_node: "finalize",
  workspace_preset_ids: ["trading_stack"],
  workspace_paths: ["/Users/example/Desktop/solana-smart-money-graph", "/Users/example/trading/logs"],
  attached_tool_ids: ["local_filesystem", "postgresql", "web_search"],
  provider_capabilities_snapshot: {
    orchestrator: { provider: "gemini", tools: { optimization_mcp: { capability: "native", tool_type: "mcp_server", name: "Optimization MCP" } } },
    researcher: {
      provider: "claude",
      tools: {
        local_filesystem: { capability: "native", tool_type: "mcp_server", name: "Local Filesystem" },
        postgresql: { capability: "native", tool_type: "mcp_server", name: "PostgreSQL" },
      },
    },
    writer: { provider: "codex", tools: { web_search: { capability: "native", tool_type: "web_search", name: "Web Search" } } },
  },
  branch_children: [
    {
      id: "sess_alpha_branch",
      mode: "board",
      status: "paused",
      created_at: 1_700_000_050,
      forked_checkpoint_id: "cp_2",
    },
  ],
};

async function mockApi(page: Page, options?: { sessions?: unknown[] }) {
  const sessions = options?.sessions ?? [];
  await page.route("http://127.0.0.1:8800/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const corsHeaders = {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
      "access-control-allow-headers": "*",
    };

    if (route.request().method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: corsHeaders,
      });
      return;
    }

    if (path === "/orchestrate/sessions") {
      await route.fulfill({ json: sessions, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/scenarios") {
      await route.fulfill({ json: scenarios, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/tools") {
      await route.fulfill({ json: configuredTools, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/tools/types") {
      await route.fulfill({ json: toolTypes, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/prompts") {
      await route.fulfill({ json: promptTemplates, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/workspaces") {
      await route.fulfill({ json: workspacePresets, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/providers/capabilities") {
      await route.fulfill({ json: providerCapabilities, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/session/sess_alpha") {
      await route.fulfill({ json: sessionDetail, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/session/sess_alpha/events") {
      await route.fulfill({
        status: 200,
        headers: { ...corsHeaders, "content-type": "text/event-stream" },
        body: "",
      });
      return;
    }
    if (path.endsWith("/control")) {
      await route.fulfill({ json: { status: "ok" }, headers: corsHeaders });
      return;
    }
    await route.fulfill({ json: [], headers: corsHeaders });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("mode selection matches premium white shell", async ({ page }) => {
  await page.unroute("http://127.0.0.1:8800/**");
  await mockApi(page, { sessions: [] });
  await page.goto("/");
  await expect(page.getByText("MODE SELECTION")).toBeVisible();
  await expect(page).toHaveScreenshot("premium-mode-selection.png", {
    fullPage: true,
    animations: "disabled",
  });
});

test("connect mcp server form matches approved shell", async ({ page }) => {
  await page.unroute("http://127.0.0.1:8800/**");
  await mockApi(page, { sessions: [] });
  await page.goto("/");
  await page.getByRole("button", { name: "Настройки" }).click();
  await expect(page.getByText("Настройки рабочего пространства")).toBeVisible();
  await page.getByRole("button", { name: /Connect MCP Server/i }).click();
  await expect(page.getByText("CONNECT MCP SERVER")).toBeVisible();
  await page.getByPlaceholder("Name").fill("Stitch MCP");
  await page.getByPlaceholder("Command/URL").fill("npx -y @modelcontextprotocol/server-github");
  await expect(page).toHaveScreenshot("premium-connect-mcp.png", {
    fullPage: true,
    animations: "disabled",
  });
});

test("session monitor matches premium board monitor", async ({ page }) => {
  await page.unroute("http://127.0.0.1:8800/**");
  await mockApi(page, { sessions: sessionSummary });
  await page.goto("/");
  await page.getByRole("button", { name: /Project Alpha/i }).click();
  await expect(page.getByText("Active MCP Connections")).toBeVisible();
  await expect(page).toHaveScreenshot("premium-session-monitor.png", {
    fullPage: true,
    animations: "disabled",
  });
});
