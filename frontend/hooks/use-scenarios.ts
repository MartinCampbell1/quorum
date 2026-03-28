import useSWR from "swr";

import { getModes, getScenarios } from "@/lib/api";
import { withScenarioFallbacks } from "@/lib/scenario-fallbacks";
import type { ScenarioDefinition } from "@/lib/types";

export function useScenarios() {
  const { data, error, isLoading } = useSWR<ScenarioDefinition[]>(
    "/orchestrate/scenarios",
    async () => {
      const [scenarios, modes] = await Promise.all([
        getScenarios(),
        getModes().catch(() => undefined),
      ]);
      return withScenarioFallbacks(scenarios, modes);
    },
    { revalidateOnFocus: false }
  );

  return { scenarios: data, error, isLoading };
}
