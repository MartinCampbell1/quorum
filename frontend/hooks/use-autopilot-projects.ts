import useSWR from "swr";

import { getAutopilotProjects } from "@/lib/api";
import type { AutopilotProjectSummary } from "@/lib/types";

export function useAutopilotProjects() {
  const { data, error, isLoading, mutate } = useSWR<AutopilotProjectSummary[]>(
    "/autopilot/projects",
    getAutopilotProjects,
    { refreshInterval: 5000 }
  );

  return { projects: data ?? [], error, isLoading, refresh: mutate };
}
