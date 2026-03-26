"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
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
      console.error("Failed:", err);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="border-t bg-background px-6 py-3.5">
      <div className="flex items-center gap-2.5">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={disabled ? "Сессия завершена" : "Отправить сообщение..."}
          disabled={disabled || sending}
          className="flex-1 rounded-lg border border-border bg-muted/20 px-4 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/50 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring transition-colors"
        />
        <Button
          size="icon"
          variant="default"
          onClick={handleSend}
          disabled={disabled || sending || !text.trim()}
          className="h-8 w-8 shrink-0"
        >
          <Send className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
