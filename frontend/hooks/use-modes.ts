import useSWR from "swr";
import { getModes } from "@/lib/api";
import type { ModeInfo } from "@/lib/types";

export function useModes() {
  const { data, error, isLoading } = useSWR<Record<string, ModeInfo>>(
    "/orchestrate/modes",
    getModes,
    { revalidateOnFocus: false }
  );
  return { modes: data, error, isLoading };
}
