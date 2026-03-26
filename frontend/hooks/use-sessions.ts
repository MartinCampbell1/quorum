import useSWR from "swr";
import { getSessions } from "@/lib/api";
import type { SessionSummary } from "@/lib/types";

export function useSessions() {
  const { data, error, isLoading, mutate } = useSWR<SessionSummary[]>(
    "/orchestrate/sessions",
    getSessions,
    { refreshInterval: 5000 }
  );
  return { sessions: data ?? [], error, isLoading, refresh: mutate };
}
