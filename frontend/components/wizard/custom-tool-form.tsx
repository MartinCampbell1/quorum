"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface CustomToolFormProps {
  onAdd: (tool: {
    key: string;
    name: string;
    description: string;
    tool_type: "http_api" | "ssh" | "shell_command";
    config: Record<string, string>;
  }) => void;
  onCancel: () => void;
}

const TOOL_TYPES = [
  { value: "http_api", label: "HTTP API" },
  { value: "ssh", label: "SSH" },
  { value: "shell_command", label: "Shell команда" },
] as const;

export function CustomToolForm({ onAdd, onCancel }: CustomToolFormProps) {
  const [toolType, setToolType] = useState<"http_api" | "ssh" | "shell_command">("http_api");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({
    url: "",
    method: "GET",
    headers: "",
    // SSH fields
    host: "",
    port: "22",
    username: "",
    // Shell fields
    command: "",
  });

  function updateConfig(key: string, value: string) {
    setConfig(prev => ({ ...prev, [key]: value }));
  }

  function handleSubmit() {
    if (!name.trim()) return;
    const key = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

    // Collect only relevant config fields
    let toolConfig: Record<string, string> = {};
    if (toolType === "http_api") {
      toolConfig = { url: config.url, method: config.method, headers: config.headers };
    } else if (toolType === "ssh") {
      toolConfig = { host: config.host, port: config.port, username: config.username };
    } else if (toolType === "shell_command") {
      toolConfig = { command: config.command };
    }

    onAdd({ key, name: name.trim(), description: description.trim() || name.trim(), tool_type: toolType, config: toolConfig });
  }

  const inputClass = "w-full rounded-lg border border-border bg-white px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring/30 transition-colors";

  return (
    <Card className="py-0 border-dashed border-foreground/20">
      <CardContent className="px-4 py-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-foreground/70">
            Новый инструмент
          </span>
          <button onClick={onCancel} aria-label="Отмена" className="p-1 rounded-md text-muted-foreground hover:text-foreground cursor-pointer">
            <X size={14} />
          </button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
          {/* Name + Type row */}
          <div className="flex gap-2 mb-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название..."
              className={`${inputClass} flex-1`}
            />
            <Select value={toolType} onValueChange={(v) => { setToolType(v as "http_api" | "ssh" | "shell_command"); }}>
              <SelectTrigger className="w-32 h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TOOL_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value} className="text-xs">
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Description */}
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Описание инструмента..."
            className={`${inputClass} mb-3`}
          />

          {/* Type-specific fields */}
          {toolType === "http_api" && (
            <div className="space-y-2 mb-3">
              <div className="flex gap-2">
                <input value={config.url} onChange={(e) => updateConfig("url", e.target.value)}
                  placeholder="https://api.example.com/endpoint" className={`${inputClass} flex-1`} />
                <Select value={config.method} onValueChange={(v) => { if (v !== null) updateConfig("method", v); }}>
                  <SelectTrigger className="w-20 h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["GET", "POST", "PUT", "DELETE"].map(m => (
                      <SelectItem key={m} value={m} className="text-xs">{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <input value={config.headers} onChange={(e) => updateConfig("headers", e.target.value)}
                placeholder='Headers JSON: {"Authorization": "Bearer ..."}' className={inputClass} />
            </div>
          )}

          {toolType === "ssh" && (
            <div className="space-y-2 mb-3">
              <div className="flex gap-2">
                <input value={config.host} onChange={(e) => updateConfig("host", e.target.value)}
                  placeholder="hostname или IP" className={`${inputClass} flex-1`} />
                <input value={config.port} onChange={(e) => updateConfig("port", e.target.value)}
                  placeholder="22" className={`${inputClass} w-16`} />
              </div>
              <input value={config.username} onChange={(e) => updateConfig("username", e.target.value)}
                placeholder="Имя пользователя" className={inputClass} />
            </div>
          )}

          {toolType === "shell_command" && (
            <div className="mb-3">
              <input value={config.command} onChange={(e) => updateConfig("command", e.target.value)}
                placeholder="Шаблон команды: curl -s {query}" className={inputClass} />
            </div>
          )}

          <Button type="submit" disabled={!name.trim()} size="sm" className="w-full text-xs">
            <Plus size={12} className="mr-1.5" /> Добавить
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
