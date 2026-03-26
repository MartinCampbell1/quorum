import useSWR from "swr";

import { getScenarios } from "@/lib/api";
import type { ScenarioDefinition } from "@/lib/types";

export function useScenarios() {
  const { data, error, isLoading } = useSWR<ScenarioDefinition[]>(
    "/orchestrate/scenarios",
    getScenarios,
    { revalidateOnFocus: false }
  );

  return { scenarios: data, error, isLoading };
}
