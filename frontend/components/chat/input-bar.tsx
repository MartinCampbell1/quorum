"use client";

import { AlertCircle } from "lucide-react";

interface InputBarProps {
  disabled: boolean;
}

export function InputBar({ disabled }: InputBarProps) {
  return (
    <div className="border-t bg-background px-6 py-3.5">
      <div className="flex items-start gap-2.5 rounded-lg border border-dashed border-border/70 bg-muted/20 px-4 py-3">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/70" />
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-foreground/80">
            {disabled ? "Сессия только для чтения." : "Живые сообщения пользователя пока не подключены в этой сборке."}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground/70">
            Журнал чата пока доступен только для наблюдения, пока backend не получит путь resume/replay.
          </p>
        </div>
      </div>
    </div>
  );
}
