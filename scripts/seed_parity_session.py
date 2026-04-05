#!/usr/bin/env python3
"""Create one synthetic Quorum session for live parity seeding."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.models import AgentConfig, SessionStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--user-message", required=True)
    parser.add_argument("--assistant-message", required=True)
    args = parser.parse_args()

    store = SessionStore()
    now = time.time()
    session_id = store.create(
        mode="creator_critic",
        task=args.task,
        agents=[
            AgentConfig(role="creator", provider="codex"),
            AgentConfig(role="critic", provider="claude"),
        ],
        config={
            "execution_mode": "seeded",
            "topology_state": {"selected_template": "parity_seed"},
            "generation_trace": {
                "trace_artifacts": [
                    {
                        "artifact_id": "seed_trace_creator",
                        "layer": "layer1",
                        "agent_role": "creator",
                        "provider": "codex",
                        "summary": "Seeded discovery candidate for full linked-chain parity.",
                        "content": "Synthetic parity seed draft.",
                        "generated_at": now,
                    }
                ]
            },
        },
    )
    store.append_messages(
        session_id,
        [
            {"role": "user", "content": args.user_message},
            {"role": "assistant", "content": args.assistant_message},
        ],
    )
    store.add_checkpoint(
        session_id,
        {
            "id": "seed_checkpoint_1",
            "timestamp": now,
            "next_node": "complete",
            "status": "ready",
            "result_preview": "Parity seed ready.",
            "graph_checkpoint_id": "seed_graph_checkpoint_1",
        },
    )
    store.append_event(
        session_id,
        "seeded",
        "Parity seed session created",
        "Synthetic discovery session for full linked-chain parity coverage.",
        status="completed",
        timestamp=now,
        agent_id="creator",
        checkpoint_id="seed_checkpoint_1",
    )
    store.update(
        session_id,
        status="completed",
        result="Synthetic parity seed session completed.",
        elapsed_sec=5.0,
        protocol_trace=[
            {
                "timestamp": now,
                "from_node_id": "seed_start",
                "to_node_id": "complete",
                "checkpoint_id": "seed_checkpoint_1",
                "ok": True,
                "guard_id": "seed_guard",
                "warnings": [],
                "errors": [],
                "state_excerpt": {"mode": "parity_seed"},
            }
        ],
        protocol_shadow_validation={"invalid_transitions": 0},
    )
    print(json.dumps({"session_id": session_id, "task": args.task}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
