"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { getSessionEventsStreamUrl } from "@/lib/api";
import type { SessionEvent } from "@/lib/types";

function sortEvents(events: SessionEvent[]): SessionEvent[] {
  return [...events].sort((a, b) => a.id - b.id);
}

function mergeEvents(current: SessionEvent[], incoming: SessionEvent[]): SessionEvent[] {
  const byId = new Map<number, SessionEvent>();
  for (const event of current) {
    byId.set(event.id, event);
  }
  for (const event of incoming) {
    byId.set(event.id, event);
  }
  return sortEvents([...byId.values()]);
}

function maxEventId(events: SessionEvent[]): number {
  return events.reduce((max, event) => Math.max(max, event.id), 0);
}

export function useSessionEvents(
  sessionId: string | null,
  initialEvents: SessionEvent[] = [],
  onEvent?: () => void
) {
  const initialSorted = useMemo(() => sortEvents(initialEvents), [initialEvents]);
  const [events, setEvents] = useState<SessionEvent[]>(initialSorted);
  const lastEventIdRef = useRef<number>(maxEventId(initialSorted));
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    const seeded = sortEvents(initialEvents);
    setEvents(seeded);
    lastEventIdRef.current = maxEventId(seeded);
    // We only reset the timeline when the session changes; ongoing snapshot
    // refreshes should merge into the live stream instead of replacing it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    setEvents((current) => {
      const merged = mergeEvents(current, initialSorted);
      lastEventIdRef.current = maxEventId(merged);
      return merged;
    });
  }, [initialSorted]);

  useEffect(() => {
    if (!sessionId) {
      return undefined;
    }

    const source = new EventSource(
      getSessionEventsStreamUrl(sessionId, lastEventIdRef.current)
    );

    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as SessionEvent;
        setEvents((current) => {
          const merged = mergeEvents(current, [event]);
          lastEventIdRef.current = maxEventId(merged);
          return merged;
        });
        onEventRef.current?.();
      } catch {
        // Ignore malformed SSE payloads and keep the stream alive.
      }
    };

    source.onerror = () => {
      source.close();
    };

    return () => {
      source.close();
    };
  }, [sessionId]);

  return { events };
}
