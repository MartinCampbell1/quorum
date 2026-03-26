"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { sendMessage } from "@/lib/api";

interface InputBarProps { sessionId: string; disabled: boolean; }

export function InputBar({ sessionId, disabled }: InputBarProps) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    if (!text.trim() || sending) return;
    setSending(true);
    try { await sendMessage(sessionId, text.trim()); setText(""); }
    catch (err) { console.error("Failed:", err); }
    finally { setSending(false); }
  }

  return (
    <div className="border-t px-4 py-3 flex items-center gap-2">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSend()}
        placeholder={disabled ? "Session ended" : "Intervene..."}
        disabled={disabled || sending}
        className="flex-1 rounded-md border bg-background px-4 py-2 text-sm placeholder:text-muted-foreground disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <Button size="icon" onClick={handleSend} disabled={disabled || sending || !text.trim()}>
        <Send className="h-4 w-4" />
      </Button>
    </div>
  );
}
