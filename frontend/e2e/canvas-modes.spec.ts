import { expect, Page, test } from "@playwright/test";

const modes = ["board", "democracy", "debate", "creator_critic", "map_reduce", "dictator", "tournament"] as const;

function buildSessionDetail(mode: string) {
  const agentSets: Record<string, { role: string; provider: string; system_prompt: string; tools: string[] }[]> = {
    board: [
      { role: "orchestrator", provider: "gemini", system_prompt: "", tools: [] },
      { role: "researcher", provider: "claude", system_prompt: "", tools: ["web_search"] },
      { role: "writer", provider: "codex", system_prompt: "", tools: [] },
    ],
    democracy: [
      { role: "voter_alpha", provider: "claude", system_prompt: "", tools: [] },
      { role: "voter_beta", provider: "gemini", system_prompt: "", tools: ["web_search"] },
      { role: "voter_gamma", provider: "codex", system_prompt: "", tools: [] },
    ],
    debate: [
      { role: "proponent", provider: "claude", system_prompt: "", tools: [] },
      { role: "opponent", provider: "gemini", system_prompt: "", tools: [] },
      { role: "judge", provider: "codex", system_prompt: "", tools: [] },
    ],
    creator_critic: [
      { role: "creator", provider: "claude", system_prompt: "", tools: [] },
      { role: "critic", provider: "gemini", system_prompt: "", tools: [] },
    ],
    map_reduce: [
      { role: "planner", provider: "claude", system_prompt: "", tools: [] },
      { role: "worker_1", provider: "gemini", system_prompt: "", tools: [] },
      { role: "worker_2", provider: "codex", system_prompt: "", tools: [] },
      { role: "synthesizer", provider: "claude", system_prompt: "", tools: [] },
    ],
    dictator: [
      { role: "dictator", provider: "claude", system_prompt: "", tools: [] },
      { role: "executor_a", provider: "gemini", system_prompt: "", tools: [] },
      { role: "executor_b", provider: "codex", system_prompt: "", tools: [] },
      { role: "executor_c", provider: "minimax", system_prompt: "", tools: [] },
    ],
    tournament: [
      { role: "contender_a", provider: "claude", system_prompt: "", tools: [] },
      { role: "contender_b", provider: "gemini", system_prompt: "", tools: [] },
      { role: "contender_c", provider: "codex", system_prompt: "", tools: [] },
      { role: "contender_d", provider: "minimax", system_prompt: "", tools: [] },
    ],
  };

  const agents = agentSets[mode] ?? agentSets.board;
  const now = Math.floor(Date.now() / 1000);

  return {
    id: "sess_canvas",
    mode,
    task: `Canvas test for ${mode} mode`,
    agents,
    messages: [
      { agent_id: agents[0]?.role ?? "agent", content: "First agent reporting analysis complete.", timestamp: now - 10, phase: "round_1" },
      ...(agents[1] ? [{ agent_id: agents[1].role, content: "Second agent confirms results.", timestamp: now - 5, phase: "round_1" }] : []),
    ],
    result: "",
    status: "running",
    config: {},
    active_scenario: null,
    forked_from: null,
    forked_checkpoint_id: null,
    capabilities: { live_messages: true, custom_tools: true, pause_resume: true, checkpoints: true, workspace_presets: true, branching: true },
    created_at: now - 120,
    elapsed_sec: 120,
    current_checkpoint_id: "cp_1",
    checkpoints: [
      { id: "cp_1", timestamp: now - 60, next_node: "process", status: "ready", result_preview: "" },
    ],
    events: [
      { id: 1, timestamp: now - 100, type: "run_started", title: "Session started", detail: `Canvas test for ${mode}`, status: "running", mode },
      { id: 2, timestamp: now - 50, type: "round_started", title: "Round 1", detail: "Processing round 1", round: 1, agent_id: agents[0]?.role },
      { id: 3, timestamp: now - 30, type: "vote_recorded", title: "Position recorded", detail: "Agent analysis submitted", agent_id: agents[0]?.role },
      { id: 4, timestamp: now - 10, type: "round_completed", title: "Round 1 complete", detail: "Round 1 consensus reached", round: 1 },
    ],
    pending_instructions: 0,
    active_node: "process",
    workspace_preset_ids: [],
    workspace_paths: [],
    attached_tool_ids: ["web_search"],
    provider_capabilities_snapshot: {},
    branch_children: [],
    attached_tools: [
      { id: "web_search", name: "Web Search", tool_type: "web_search", transport: "native", subtitle: "Search", icon: "🔍", capability: "native" },
    ],
  };
}

async function mockApiForMode(page: Page, mode: string) {
  const sessionDetail = buildSessionDetail(mode);
  const sessionSummary = [
    {
      id: "sess_canvas",
      mode,
      task: `Canvas test for ${mode} mode`,
      status: "running",
      created_at: sessionDetail.created_at,
      active_scenario: null,
      forked_from: null,
    },
  ];

  await page.route("http://127.0.0.1:8800/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const corsHeaders = {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,POST,PUT,DELETE,OPTIONS",
      "access-control-allow-headers": "*",
    };

    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/sessions") {
      await route.fulfill({ json: sessionSummary, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/scenarios") {
      await route.fulfill({ json: [], headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/tools") {
      await route.fulfill({ json: [], headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/tools/types") {
      await route.fulfill({ json: {}, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/prompts") {
      await route.fulfill({ json: {}, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/workspaces") {
      await route.fulfill({ json: [], headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/settings/providers/capabilities") {
      await route.fulfill({ json: { providers: [], tools: {} }, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/session/sess_canvas") {
      await route.fulfill({ json: sessionDetail, headers: corsHeaders });
      return;
    }
    if (path === "/orchestrate/session/sess_canvas/events") {
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
  await page.emulateMedia({ reducedMotion: "reduce" });
});

for (const mode of modes) {
  test(`canvas ${mode} renders correctly`, async ({ page }) => {
    await mockApiForMode(page, mode);
    await page.goto("/");

    const taskText = `Canvas test for ${mode}`;
    await page.getByRole("button", { name: new RegExp(taskText.slice(0, 20), "i") }).click();

    // Wait for the topology panel to load
    await page.waitForTimeout(800);

    await expect(page).toHaveScreenshot(`canvas-${mode}.png`, {
      fullPage: true,
      animations: "disabled",
    });
  });
}
