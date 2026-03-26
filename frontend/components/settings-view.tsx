"use client";

import { Badge } from "@/components/ui/badge";

export function SettingsView() {
  return (
    <div className="flex flex-col h-full">
      <div className="border-b bg-background px-8 py-4">
        <h2 className="text-lg font-semibold tracking-tight">Настройки</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Конфигурация приложения
        </p>
      </div>
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-lg space-y-6">
          <div className="rounded-xl border border-border p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium">Бэкенд API</h3>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal border-green-500/30 text-green-600">
                Подключён
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
              <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
              http://localhost:8800
            </div>
          </div>

          <div className="rounded-xl border border-border p-5">
            <h3 className="text-sm font-medium mb-3">О приложении</h3>
            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex justify-between">
                <span>Версия</span>
                <span className="font-mono">0.1.0</span>
              </div>
              <div className="flex justify-between">
                <span>Фронтенд</span>
                <span className="font-mono">Next.js 16 + shadcn/ui</span>
              </div>
              <div className="flex justify-between">
                <span>Оркестратор</span>
                <span className="font-mono">LangGraph + FastAPI</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
