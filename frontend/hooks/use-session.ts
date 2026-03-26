import useSWR from "swr";
import { getSession } from "@/lib/api";
import type { Session } from "@/lib/types";

export function useSession(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Session>(
    id ? `/orchestrate/session/${id}` : null,
    id ? () => getSession(id) : null,
    {
      refreshInterval: (data) => (data?.status === "running" ? 2000 : 0),
    }
  );
  return { session: data ?? null, error, isLoading, refresh: mutate };
}
