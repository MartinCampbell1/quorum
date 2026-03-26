"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { sendMessage } from "@/lib/api";

interface InputBarProps {
  sessionId: string;
  disabled: boolean;
}

export function InputBar({ sessionId, disabled }: InputBarProps) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      await sendMessage(sessionId, text.trim());
      setText("");
    } catch (err) {
      console.error("Failed to send:", err);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="border-t border-border px-4 py-3">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={
            disabled ? "Session ended" : "Intervene in conversation..."
          }
          disabled={disabled || sending}
          className="flex-1 rounded-lg border border-border bg-bg-card px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-40"
        />
        <button
          onClick={handleSend}
          disabled={disabled || sending || !text.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-40 cursor-pointer"
          aria-label="Send message"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
