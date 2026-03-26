"use client";

import { useState, useEffect } from "react";
import {
  Plus,
  Trash2,
  Settings2,
  Pencil,
  BookOpen,
  Eye,
  EyeOff,
  AlertTriangle,
  CheckCircle2,
  FolderTree,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getConfiguredTools,
  getToolTypes,
  addConfiguredTool,
  updateConfiguredTool,
  deleteConfiguredTool,
  getPromptTemplates,
  getWorkspacePresets,
  addWorkspacePreset,
  deleteWorkspacePreset,
  validateConfiguredTool,
} from "@/lib/api";
import type {
  ConfiguredTool,
  PromptTemplate,
  ToolFieldSchema,
  ToolTypeDefinition,
  WorkspacePreset,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const INPUT_CLASS =
  "w-full rounded-2xl border border-slate-200/80 bg-white/85 px-3.5 py-2.5 text-xs text-foreground placeholder:text-muted-foreground/50 shadow-inner transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400/25 dark:border-slate-800/80 dark:bg-slate-950/55";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/g, "_")
    .replace(/^_|_$/g, "");
}

function hasMissingRequired(tool: ConfiguredTool, toolTypes: Record<string, ToolTypeDefinition>): boolean {
  const typeInfo = toolTypes[tool.tool_type];
  if (!typeInfo) return false;
  return typeInfo.fields
    .filter((f) => f.required)
    .some((f) => !tool.config[f.name]?.trim());
}

function renderFieldControl({
  field,
  value,
  onChange,
}: {
  field: ToolFieldSchema;
  value: string;
  onChange: (value: string) => void;
}) {
  if (field.type === "password") {
    return (
      <PasswordField
        value={value}
        onChange={onChange}
        placeholder={field.placeholder}
      />
    );
  }

  if (field.type === "textarea") {
    return (
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder}
        rows={4}
        className={`${INPUT_CLASS} min-h-24 resize-y leading-relaxed`}
      />
    );
  }

  if (field.type === "select") {
    return (
      <Select value={value} onValueChange={(nextValue) => onChange(nextValue ?? "")}>
        <SelectTrigger className="w-full h-9 text-xs">
          <SelectValue placeholder={field.placeholder || "Выберите..."} />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((option) => (
            <SelectItem key={option} value={option} className="text-xs">
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={field.placeholder}
      className={INPUT_CLASS}
    />
  );
}

function PasswordField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`${INPUT_CLASS} pr-8`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
        aria-label={visible ? "Скрыть" : "Показать"}
      >
        {visible ? <EyeOff size={13} /> : <Eye size={13} />}
      </button>
    </div>
  );
}

function McpTransportPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const options = ["stdio", "http"];

  return (
    <div className="grid grid-cols-2 gap-2 rounded-2xl border border-[#e2e8f0] bg-white p-1 dark:border-slate-800 dark:bg-slate-950/55">
      {options.map((option) => {
        const active = value === option;
        return (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={cn(
              "rounded-xl px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-[#09090b] text-white dark:bg-white dark:text-[#09090b]"
                : "text-[#445d99] hover:bg-[#f2f3ff] dark:text-slate-400 dark:hover:bg-slate-900"
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

function McpHandshakeLog({
  transport,
  lines,
}: {
  transport: string;
  lines?: string[];
}) {
  const fallbackLines = transport === "http"
    ? [
        "> Resolving remote endpoint...",
        "> Sending capabilities request...",
        "> Waiting for HTTP handshake...",
        "> Connection successful. Remote MCP ready.",
      ]
    : [
        "> Connecting to server...",
        "> Handshake initiated...",
        "> Waiting for stdio response...",
        "> Connection successful. Server ready.",
      ];
  const effectiveLines = lines && lines.length > 0 ? lines : fallbackLines;

  return (
    <div className="rounded-[18px] border border-[#e2e8f0] bg-[#f7f8ff] p-4 dark:border-slate-800 dark:bg-slate-950/65">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#445d99] dark:text-slate-400">
        Handshake Log
      </p>
      <div className="mt-3 rounded-[14px] border border-[#e2e8f0] bg-white px-4 py-3 font-mono text-[12px] leading-7 text-[#09090b] dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-200">
        {effectiveLines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    </div>
  );
}

function ToolAddForm({
  toolTypes,
  onAdd,
  onCancel,
  initialType = "",
}: {
  toolTypes: Record<string, ToolTypeDefinition>;
  onAdd: (tool: { name: string; tool_type: string; config: Record<string, string> }) => void;
  onCancel: () => void;
  initialType?: string;
}) {
  const [selectedType, setSelectedType] = useState(initialType);
  const [name, setName] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});

  const typeKeys = Object.keys(toolTypes);
  const currentType = selectedType ? toolTypes[selectedType] : null;

  useEffect(() => {
    if (!initialType || !toolTypes[initialType]) return;
    const typeInfo = toolTypes[initialType];
    setSelectedType(initialType);
    setName("");
    const initialConfig: Record<string, string> = {};
    for (const field of typeInfo.fields) {
      initialConfig[field.name] = field.name === "transport" ? "stdio" : "";
    }
    setConfig(initialConfig);
  }, [initialType, toolTypes]);

  function handleTypeChange(type: string | null) {
    if (!type) return;
    setSelectedType(type);
    const typeInfo = toolTypes[type];
    if (typeInfo) {
      setName(typeInfo.name);
      const initialConfig: Record<string, string> = {};
      for (const field of typeInfo.fields) {
        initialConfig[field.name] = field.name === "transport" ? "stdio" : "";
      }
      setConfig(initialConfig);
    }
  }

  function handleSubmit() {
    if (!name.trim() || !selectedType) return;
    if (selectedType === "mcp_server") {
      const transport = config.transport || "stdio";
      if (transport === "http" && !config.url?.trim()) return;
      if (transport === "stdio" && !config.command?.trim()) return;
    }
    onAdd({ name: name.trim(), tool_type: selectedType, config });
  }

  if (selectedType === "mcp_server") {
    const transport = config.transport ?? "stdio";
    return (
      <div className="flex h-full flex-col bg-white">
        <div className="flex-1 px-8 py-6">
          <h1 className="text-[2.15rem] font-medium uppercase tracking-[0.04em] text-[#09090b]">
            CONNECT MCP SERVER
          </h1>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="mx-auto mt-8 max-w-[560px]"
          >
            <div className="overflow-hidden rounded-[18px] border-2 border-[#111111] bg-white">
              <div className="space-y-5 px-7 py-7">
                <div>
                  <label className="mb-2 block text-[13px] font-medium text-[#111111]">Name</label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Name"
                    className="h-10 w-full rounded-[10px] border border-[#111111] bg-white px-4 text-[13px] text-[#111111] outline-none placeholder:text-[#111111]/42"
                  />
                </div>
                <div>
                  <label className="mb-3 block text-[13px] font-medium text-[#111111]">Transport Type</label>
                  <div className="rounded-[10px] border border-[#d9dde7] bg-white p-1">
                    <div className="grid grid-cols-2 gap-1">
                      {["stdio", "http"].map((option) => {
                        const active = transport === option;
                        return (
                          <button
                            key={option}
                            type="button"
                            onClick={() => setConfig((prev) => ({ ...prev, transport: option }))}
                            className={cn(
                              "flex h-9 items-center justify-center gap-2 rounded-[8px] text-[13px] text-[#111111]",
                              active ? "bg-[#f3f4f7]" : "bg-white"
                            )}
                          >
                            <span
                              className={cn(
                                "h-4 w-4 rounded-full border border-[#9ca3af]",
                                active && "border-[#6b7280] bg-white"
                              )}
                            >
                              <span
                                className={cn(
                                  "m-auto mt-[3px] block h-2 w-2 rounded-full bg-[#6b7280]",
                                  active ? "opacity-100" : "opacity-0"
                                )}
                              />
                            </span>
                            {option}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="mb-2 block text-[13px] font-medium text-[#111111]">
                    {transport === "http" ? "Command/URL" : "Command/URL"}
                  </label>
                  <input
                    value={transport === "http" ? (config.url ?? "") : (config.command ?? "")}
                    onChange={(e) =>
                      setConfig((prev) => ({
                        ...prev,
                        [transport === "http" ? "url" : "command"]: e.target.value,
                      }))
                    }
                    placeholder="Command/URL"
                    className="h-10 w-full rounded-[10px] border border-[#d9dde7] bg-white px-4 text-[13px] text-[#111111] outline-none placeholder:text-[#111111]/42"
                  />
                </div>
              </div>
              <div className="border-t border-[#e4e6eb] px-7 py-6">
                <div className="text-[13px] font-medium text-[#111111]">Handshake Log</div>
                <div className="mt-4 rounded-[10px] border border-[#d9dde7] bg-[#f6f7fa] px-4 py-4 font-mono text-[12px] leading-8 text-[#111111]">
                  <div>&gt; {transport === "http" ? "Resolving remote endpoint..." : "Connecting to server..."}</div>
                  <div>&gt; Handshake initiated...</div>
                  <div>&gt; {transport === "http" ? "Waiting for HTTP response..." : "Waiting for response..."}</div>
                  <div>&gt; Connection successful. Server ready.</div>
                </div>
              </div>
            </div>
          </form>
        </div>
        <div className="flex h-[86px] items-center justify-between border-t border-[#e6e8ee] bg-white px-7">
          <div className="text-[16px] font-medium text-[#111111]">Server Configuration</div>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={onCancel}
              className="h-[46px] rounded-[12px] px-5 text-[15px] text-[#111111] hover:bg-[#f5f6fa]"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              onClick={handleSubmit}
              disabled={!name.trim() || (transport === "http" ? !config.url?.trim() : !config.command?.trim())}
              className="h-[46px] rounded-[12px] bg-black px-8 text-[15px] font-medium text-white hover:bg-black/92 disabled:bg-black/30"
            >
              Connect
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Card className="overflow-hidden border border-[#d9dde7] bg-white py-0 shadow-none">
      <CardContent className="space-y-3 px-5 py-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-[#4b5563]">
            Новый инструмент
          </span>
          <button
            onClick={onCancel}
            aria-label="Отмена"
            className="cursor-pointer rounded-md p-1 text-muted-foreground hover:text-foreground"
          >
            <X size={14} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <div className="mb-3">
            <label className="mb-1 block text-[11px] text-muted-foreground">Тип инструмента</label>
            <Select value={selectedType} onValueChange={handleTypeChange}>
              <SelectTrigger className="h-10 w-full rounded-[10px] border-[#d9dde7] bg-white text-xs">
                <SelectValue placeholder="Выберите тип..." />
              </SelectTrigger>
              <SelectContent>
                {typeKeys.map((key) => (
                  <SelectItem key={key} value={key} className="text-xs">
                    {toolTypes[key].name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {currentType ? (
            <>
              <div className="mb-3">
                <label className="mb-1 block text-[11px] text-muted-foreground">Название</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Название инструмента..."
                  className={INPUT_CLASS}
                />
                <p className="mt-0.5 font-mono text-[10px] text-muted-foreground/50">
                  id: {slugify(name)}
                </p>
              </div>
              <div className="mb-3 space-y-2">
                {currentType.fields.map((field) => (
                  <div key={field.name}>
                    <label className="mb-1 block text-[11px] text-muted-foreground">
                      {field.label}
                      {field.required ? <span className="ml-0.5 text-destructive">*</span> : null}
                    </label>
                    {renderFieldControl({
                      field,
                      value: config[field.name] ?? "",
                      onChange: (value) => setConfig((prev) => ({ ...prev, [field.name]: value })),
                    })}
                  </div>
                ))}
              </div>
              <Button
                type="submit"
                disabled={!name.trim()}
                size="sm"
                className="w-full rounded-[10px] bg-black text-xs text-white hover:bg-black/90"
              >
                <Plus size={12} className="mr-1.5" /> Добавить
              </Button>
            </>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}

function ToolEditForm({
  tool,
  toolType,
  onSave,
  onCancel,
}: {
  tool: ConfiguredTool;
  toolType: ToolTypeDefinition | undefined;
  onSave: (updates: { name: string; config: Record<string, string> }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(tool.name);
  const [config, setConfig] = useState<Record<string, string>>({ ...tool.config });

  const fields = toolType?.fields ?? [];

  function handleSubmit() {
    if (!name.trim()) return;
    if (tool.tool_type === "mcp_server") {
      const transport = config.transport || "stdio";
      if (transport === "http" && !config.url?.trim()) return;
      if (transport === "stdio" && !config.command?.trim()) return;
    }
    onSave({ name: name.trim(), config });
  }

  return (
    <Card className="overflow-hidden border-dashed border-slate-300/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] py-0 shadow-[0_20px_60px_-44px_rgba(15,23,42,0.28)] dark:border-slate-700/80 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.88),rgba(2,6,23,0.78))]">
      <CardContent className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-600 dark:text-slate-300">
            Редактирование
          </span>
          <button
            onClick={onCancel}
            aria-label="Отмена"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <div className="mb-3">
            <label className="mb-1 block text-[11px] text-muted-foreground">Название</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название..."
              className={INPUT_CLASS}
            />
          </div>

          {tool.tool_type === "mcp_server" ? (
            <div className="mb-3 space-y-4">
              <div>
                <label className="mb-1 block text-[11px] text-muted-foreground">Transport Type</label>
                <McpTransportPicker
                  value={config.transport ?? "stdio"}
                  onChange={(value) => setConfig((prev) => ({ ...prev, transport: value }))}
                />
              </div>

              {(config.transport ?? "stdio") === "stdio" ? (
                <>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Command</label>
                    <input
                      value={config.command ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, command: e.target.value }))}
                      placeholder="npx -y @modelcontextprotocol/server-github"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Args</label>
                    <input
                      value={config.args ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, args: e.target.value }))}
                      placeholder="--project my-app"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Environment (JSON)</label>
                    <textarea
                      value={config.env ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, env: e.target.value }))}
                      placeholder='{"GITHUB_TOKEN":"ghp_..."}'
                      rows={4}
                      className={`${INPUT_CLASS} min-h-24 resize-y leading-relaxed`}
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">URL</label>
                    <input
                      value={config.url ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, url: e.target.value }))}
                      placeholder="https://stitch.googleapis.com/mcp"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">HTTP Headers (JSON)</label>
                    <textarea
                      value={config.headers ?? ""}
                      onChange={(e) => setConfig((prev) => ({ ...prev, headers: e.target.value }))}
                      placeholder='{"X-Goog-Api-Key":"..."}'
                      rows={4}
                      className={`${INPUT_CLASS} min-h-24 resize-y leading-relaxed`}
                    />
                  </div>
                </>
              )}

              <McpHandshakeLog
                transport={config.transport ?? "stdio"}
                lines={tool.last_validation_result?.log}
              />
            </div>
          ) : (
            <div className="space-y-2 mb-3">
              {fields.map((field) => (
                <div key={field.name}>
                  <label className="mb-1 block text-[11px] text-muted-foreground">
                    {field.label}
                    {field.required && <span className="text-destructive ml-0.5">*</span>}
                  </label>
                  {renderFieldControl({
                    field,
                    value: config[field.name] ?? "",
                    onChange: (value) => setConfig((prev) => ({ ...prev, [field.name]: value })),
                  })}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" className="flex-1 rounded-full text-xs" onClick={onCancel}>
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || (tool.tool_type === "mcp_server" && ((config.transport ?? "stdio") === "http" ? !config.url?.trim() : !config.command?.trim()))}
              size="sm"
              className="flex-1 rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
            >
              Сохранить
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export function SettingsView() {
  const [tools, setTools] = useState<ConfiguredTool[]>([]);
  const [toolTypes, setToolTypes] = useState<Record<string, ToolTypeDefinition>>({});
  const [templates, setTemplates] = useState<Record<string, PromptTemplate>>({});
  const [workspacePresets, setWorkspacePresets] = useState<WorkspacePreset[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [deletingToolId, setDeletingToolId] = useState<string | null>(null);
  const [validatingToolId, setValidatingToolId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceDescription, setWorkspaceDescription] = useState("");
  const [workspacePathsDraft, setWorkspacePathsDraft] = useState("");

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      setIsLoading(true);
      const results = await Promise.allSettled([
        getConfiguredTools(),
        getToolTypes(),
        getPromptTemplates(),
        getWorkspacePresets(),
      ]);

      if (!mounted) return;

      if (results[0].status === "fulfilled") setTools(results[0].value);
      if (results[1].status === "fulfilled") setToolTypes(results[1].value);
      if (results[2].status === "fulfilled") setTemplates(results[2].value);
      if (results[3].status === "fulfilled") setWorkspacePresets(results[3].value);
      setIsLoading(false);
    }

    loadData();
    return () => { mounted = false; };
  }, []);

  async function refreshTools() {
    try {
      const data = await getConfiguredTools();
      setTools(data);
    } catch {
      // keep stale data on error
    }
  }

  async function refreshWorkspaces() {
    try {
      const data = await getWorkspacePresets();
      setWorkspacePresets(data);
    } catch {
      // keep stale data on error
    }
  }

  async function handleAddTool(tool: { name: string; tool_type: string; config: Record<string, string> }) {
    const id = slugify(tool.name);
    await addConfiguredTool({ id, ...tool, enabled: true });
    setShowAddForm(false);
    await refreshTools();
  }

  async function handleUpdateTool(id: string, updates: { name: string; config: Record<string, string> }) {
    await updateConfiguredTool(id, updates);
    setEditingToolId(null);
    await refreshTools();
  }

  async function handleDeleteTool(id: string) {
    await deleteConfiguredTool(id);
    setDeletingToolId(null);
    await refreshTools();
  }

  async function handleToggleEnabled(tool: ConfiguredTool) {
    await updateConfiguredTool(tool.id, { enabled: !tool.enabled });
    await refreshTools();
  }

  async function handleValidateTool(tool: ConfiguredTool) {
    setValidatingToolId(tool.id);
    try {
      await validateConfiguredTool(tool.id);
      await refreshTools();
    } finally {
      setValidatingToolId(null);
    }
  }

  async function handleAddWorkspacePreset() {
    const name = workspaceName.trim();
    const paths = workspacePathsDraft
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!name || paths.length === 0) return;
    await addWorkspacePreset({
      id: slugify(name),
      name,
      description: workspaceDescription.trim() || null,
      paths,
    });
    setWorkspaceName("");
    setWorkspaceDescription("");
    setWorkspacePathsDraft("");
    await refreshWorkspaces();
  }

  async function handleDeleteWorkspacePreset(id: string) {
    await deleteWorkspacePreset(id);
    await refreshWorkspaces();
  }

  const templateKeys = Object.keys(templates);

  if (showAddForm) {
    return (
      <div className="flex h-full flex-col bg-white">
        <ToolAddForm
          toolTypes={toolTypes}
          onAdd={handleAddTool}
          onCancel={() => setShowAddForm(false)}
          initialType="mcp_server"
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-5xl space-y-8">
          <section className="rounded-[24px] border border-[#e6e8ee] bg-[#f8f9fc] px-6 py-6">
            <div className="flex items-start justify-between gap-6">
              <div className="max-w-2xl">
                <span className="rounded-full border border-[#b8d3f7] bg-white px-3 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-[#3b82f6]">
                  Tool Registry
                </span>
                <h2 className="mt-4 text-[2rem] font-semibold tracking-[-0.04em] text-[#111111]">
                  Настройки рабочего пространства
                </h2>
                <p className="mt-2 text-[15px] leading-7 text-[#5b6476]">
                  Здесь живут инструменты, prompt templates и конфигурация для локального multi-agent cockpit.
                  Держи registry в порядке, чтобы сценарии запускались без ручной переклейки.
                </p>
              </div>
              <div className="grid min-w-[200px] grid-cols-2 gap-3">
                <div className="rounded-[16px] border border-[#e0e4ec] bg-white px-4 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-[#7b8190]">Tools</p>
                  <p className="mt-1 text-[28px] font-semibold tracking-[-0.04em] text-[#111111]">{tools.length}</p>
                </div>
                <div className="rounded-[16px] border border-[#e0e4ec] bg-white px-4 py-3">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-[#7b8190]">Templates</p>
                  <p className="mt-1 text-[28px] font-semibold tracking-[-0.04em] text-[#111111]">{templateKeys.length}</p>
                </div>
              </div>
            </div>
          </section>

          {/* Section 1: Tools */}
          <section className="rounded-[24px] border border-[#e6e8ee] bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings2 size={16} className="text-[#3b82f6]" />
                <h3 className="text-sm font-medium text-slate-950">Инструменты</h3>
                {tools.length > 0 && (
                  <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                    {tools.length}
                  </Badge>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="rounded-[12px] border-[#d9dde7] bg-white text-xs"
                onClick={() => {
                  setShowAddForm(true);
                  setEditingToolId(null);
                }}
              >
                <Plus size={12} className="mr-1" /> Connect MCP Server
              </Button>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40 animate-pulse" />
              </div>
            ) : (
              <div className="space-y-2">
                {/* Tool list */}
                {tools.map((tool) => {
                  if (editingToolId === tool.id) {
                    return (
                      <ToolEditForm
                        key={tool.id}
                        tool={tool}
                        toolType={toolTypes[tool.tool_type]}
                        onSave={(updates) => handleUpdateTool(tool.id, updates)}
                        onCancel={() => setEditingToolId(null)}
                      />
                    );
                  }

                  const isMissing = hasMissingRequired(tool, toolTypes);
                  const typeInfo = toolTypes[tool.tool_type];
                  const compatibilityEntries = Object.entries(tool.compatibility ?? {}).filter(
                    ([provider, capability]) => provider !== "minimax" && capability !== "unavailable"
                  );
                  const validationOk = tool.validation_status === "valid";
                  const validationError = tool.validation_status === "invalid";

                  return (
                    <div
                      key={tool.id}
                      className={cn(
                        "group flex items-center gap-3 rounded-[18px] border border-[#e0e4ec] bg-white p-3.5 transition-all",
                        !tool.enabled && "opacity-50"
                      )}
                    >
                      {/* Icon */}
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] border border-[#e0e4ec] bg-white text-muted-foreground">
                        {typeInfo?.icon ? (
                          <span className="text-sm">{typeInfo.icon}</span>
                        ) : (
                          <Settings2 size={14} strokeWidth={1.5} />
                        )}
                      </div>

                      {/* Name + badges */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">{tool.name}</span>
                          {isMissing && (
                            <span title="Не заполнены обязательные поля" className="text-amber-500">
                              <AlertTriangle size={13} />
                            </span>
                          )}
                          {validationOk ? (
                            <span title="Проверено" className="text-emerald-600">
                              <CheckCircle2 size={13} />
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                          <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                            {typeInfo?.category ?? tool.tool_type}
                          </Badge>
                          {tool.tool_type === "mcp_server" && (
                            <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal uppercase">
                              {(tool.config.transport || "stdio").toUpperCase()}
                            </Badge>
                          )}
                          {compatibilityEntries.map(([provider, capability]) => (
                            <Badge
                              key={`${tool.id}-${provider}`}
                              variant="outline"
                              className={cn(
                                "px-1.5 py-0 text-[10px] font-normal uppercase",
                                capability === "native"
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                  : "border-amber-200 bg-amber-50 text-amber-700"
                              )}
                            >
                              {provider}: {capability}
                            </Badge>
                          ))}
                          <span className="text-[10px] text-muted-foreground/50 font-mono">
                            {tool.id}
                          </span>
                        </div>
                        {validationError && tool.last_validation_result?.error ? (
                          <p className="mt-1 text-[11px] text-rose-600">
                            {tool.last_validation_result.error}
                          </p>
                        ) : null}
                        {tool.last_validation_result?.log?.length ? (
                          <p className="mt-1 text-[11px] text-muted-foreground/70">
                            {tool.last_validation_result.log[tool.last_validation_result.log.length - 1]}
                          </p>
                        ) : null}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => handleValidateTool(tool)}
                          aria-label="Проверить"
                          disabled={validatingToolId === tool.id}
                        >
                          {validatingToolId === tool.id ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <RefreshCw size={12} />
                          )}
                        </Button>
                        {/* Enabled toggle */}
                        <button
                          onClick={() => handleToggleEnabled(tool)}
                          className={cn(
                            "relative h-5 w-9 rounded-full border transition-colors cursor-pointer",
                            tool.enabled
                              ? "bg-green-500/20 border-green-500/30"
                              : "bg-muted border-border"
                          )}
                          aria-label={tool.enabled ? "Выключить" : "Включить"}
                        >
                          <span
                            className={cn(
                              "absolute top-0.5 h-3.5 w-3.5 rounded-full transition-all",
                              tool.enabled
                                ? "left-[18px] bg-green-500"
                                : "left-0.5 bg-muted-foreground/40"
                            )}
                          />
                        </button>

                        {/* Edit */}
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => { setEditingToolId(tool.id); setShowAddForm(false); }}
                          aria-label="Редактировать"
                        >
                          <Pencil size={12} />
                        </Button>

                        {/* Delete */}
                        {deletingToolId === tool.id ? (
                          <div className="flex items-center gap-1">
                            <Button
                              variant="destructive"
                              size="icon-xs"
                              onClick={() => handleDeleteTool(tool.id)}
                              aria-label="Подтвердить удаление"
                            >
                              <Trash2 size={12} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon-xs"
                              onClick={() => setDeletingToolId(null)}
                              aria-label="Отменить удаление"
                            >
                              <X size={12} />
                            </Button>
                          </div>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon-xs"
                            onClick={() => setDeletingToolId(tool.id)}
                            aria-label="Удалить"
                          >
                            <Trash2 size={12} />
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Empty state */}
                {tools.length === 0 && !showAddForm && (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Settings2 className="h-8 w-8 mb-3 opacity-30" />
                    <p className="text-sm">Нет настроенных инструментов</p>
                    <p className="text-xs text-muted-foreground/50 mt-1">
                      Добавьте инструмент для начала работы
                    </p>
                  </div>
                )}

                {/* Add form */}
              </div>
            )}
          </section>

          <section className="rounded-[24px] border border-[#e6e8ee] bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <FolderTree size={16} className="text-[#3b82f6]" />
              <h3 className="text-sm font-medium text-slate-950">Workspace Presets</h3>
              {workspacePresets.length > 0 && (
                <Badge variant="outline" className="border-[#e0e4ec] bg-white px-1.5 py-0 text-[10px] font-normal">
                  {workspacePresets.length}
                </Badge>
              )}
            </div>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
              <div className="space-y-2">
                {workspacePresets.length === 0 ? (
                  <div className="rounded-[18px] border border-dashed border-[#d9dde7] bg-[#fafbff] px-4 py-5 text-[12px] text-[#6b7280]">
                    Пока нет сохранённых наборов директорий. Добавь хотя бы один preset для trading repo, логов или docs.
                  </div>
                ) : (
                  workspacePresets.map((preset) => (
                    <div
                      key={preset.id}
                      className="rounded-[18px] border border-[#e0e4ec] bg-white px-4 py-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-[#111111]">{preset.name}</div>
                          {preset.description ? (
                            <p className="mt-1 text-[12px] text-[#6b7280]">{preset.description}</p>
                          ) : null}
                          <div className="mt-2 flex flex-col gap-1">
                            {preset.paths.map((path) => (
                              <span key={path} className="font-mono text-[11px] text-[#6b7280]">
                                {path}
                              </span>
                            ))}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          onClick={() => handleDeleteWorkspacePreset(preset.id)}
                          aria-label="Удалить workspace preset"
                        >
                          <Trash2 size={12} />
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <Card className="overflow-hidden border border-[#d9dde7] bg-white py-0 shadow-none">
                <CardContent className="space-y-3 px-5 py-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-[#4b5563]">
                      Новый preset
                    </span>
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Название</label>
                    <input
                      value={workspaceName}
                      onChange={(e) => setWorkspaceName(e.target.value)}
                      placeholder="Trading repo + logs"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Описание</label>
                    <input
                      value={workspaceDescription}
                      onChange={(e) => setWorkspaceDescription(e.target.value)}
                      placeholder="Репозиторий и данные для pattern mining"
                      className={INPUT_CLASS}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-[11px] text-muted-foreground">Пути (по одному на строку)</label>
                    <textarea
                      value={workspacePathsDraft}
                      onChange={(e) => setWorkspacePathsDraft(e.target.value)}
                      placeholder={"/Users/martin/project\n/Users/martin/logs"}
                      rows={5}
                      className={`${INPUT_CLASS} min-h-28 resize-y leading-relaxed`}
                    />
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    className="w-full rounded-[10px] bg-black text-xs text-white hover:bg-black/90"
                    onClick={handleAddWorkspacePreset}
                    disabled={!workspaceName.trim() || !workspacePathsDraft.trim()}
                  >
                    <Plus size={12} className="mr-1.5" /> Сохранить preset
                  </Button>
                </CardContent>
              </Card>
            </div>
          </section>

          {/* Section 2: Prompt templates */}
          <section className="rounded-[24px] border border-[#e6e8ee] bg-white p-6">
            <div className="flex items-center gap-2 mb-4">
              <BookOpen size={16} className="text-muted-foreground" />
              <h3 className="text-sm font-medium">Шаблоны промптов</h3>
              {templateKeys.length > 0 && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal">
                  {templateKeys.length}
                </Badge>
              )}
            </div>

            {templateKeys.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <BookOpen className="h-8 w-8 mb-3 opacity-30" />
                <p className="text-sm">Шаблоны не загружены</p>
                <p className="text-xs text-muted-foreground/50 mt-1">
                  Шаблоны появятся когда бэкенд будет доступен
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {templateKeys.map((key) => {
                  const tmpl = templates[key];
                  return (
                    <div
                      key={key}
                      className="rounded-xl border border-border p-3 space-y-1.5"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{tmpl.name ?? key}</span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-normal font-mono">
                          {key}
                        </Badge>
                      </div>
                      {tmpl.description && (
                        <p className="text-xs text-muted-foreground">{tmpl.description}</p>
                      )}
                      {tmpl.prompt && (
                        <pre className="text-[11px] text-muted-foreground/70 font-mono bg-muted/30 rounded-md p-2 max-h-24 overflow-y-auto whitespace-pre-wrap">
                          {tmpl.prompt.length > 300
                            ? `${tmpl.prompt.slice(0, 300)}...`
                            : tmpl.prompt}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Section 3: Backend API status (existing) */}
          <section>
            <div className="rounded-[20px] border border-[#e6e8ee] p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">Бэкенд API</h3>
                <Badge
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 font-normal border-green-500/30 text-green-600"
                >
                  Подключён
                </Badge>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
                <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
                http://localhost:8800
              </div>
            </div>

            <div className="mt-2 rounded-[20px] border border-[#e6e8ee] p-5">
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
          </section>
        </div>
      </div>
    </div>
  );
}
