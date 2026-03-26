"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, Settings2, Pencil, BookOpen, Eye, EyeOff, AlertTriangle, X } from "lucide-react";
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
} from "@/lib/api";
import type {
  ConfiguredTool,
  PromptTemplate,
  ToolFieldSchema,
  ToolTypeDefinition,
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

function ToolAddForm({
  toolTypes,
  onAdd,
  onCancel,
}: {
  toolTypes: Record<string, ToolTypeDefinition>;
  onAdd: (tool: { name: string; tool_type: string; config: Record<string, string> }) => void;
  onCancel: () => void;
}) {
  const [selectedType, setSelectedType] = useState("");
  const [name, setName] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});

  const typeKeys = Object.keys(toolTypes);
  const currentType = selectedType ? toolTypes[selectedType] : null;

  function handleTypeChange(type: string | null) {
    if (!type) return;
    setSelectedType(type);
    const typeInfo = toolTypes[type];
    if (typeInfo) {
      setName(typeInfo.name);
      const initialConfig: Record<string, string> = {};
      for (const field of typeInfo.fields) {
        initialConfig[field.name] = "";
      }
      setConfig(initialConfig);
    }
  }

  function handleSubmit() {
    if (!name.trim() || !selectedType) return;
    onAdd({ name: name.trim(), tool_type: selectedType, config });
  }

  return (
    <Card className="overflow-hidden border-dashed border-sky-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(241,245,249,0.92))] py-0 shadow-[0_20px_60px_-44px_rgba(14,165,233,0.35)] dark:border-sky-900/60 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.88),rgba(2,6,23,0.78))]">
      <CardContent className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-700 dark:text-sky-300">
            Новый инструмент
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
          {/* Tool type selector */}
          <div className="mb-3">
            <label className="mb-1 block text-[11px] text-muted-foreground">Тип инструмента</label>
            <Select value={selectedType} onValueChange={handleTypeChange}>
              <SelectTrigger className="h-10 w-full rounded-2xl border-slate-200/80 bg-white/85 text-xs dark:border-slate-800 dark:bg-slate-950/55">
                <SelectValue placeholder="Выберите тип..." />
              </SelectTrigger>
              <SelectContent>
                {typeKeys.map((key) => (
                  <SelectItem key={key} value={key} className="text-xs">
                    {toolTypes[key].name}
                    {toolTypes[key].category && (
                      <span className="ml-1 text-muted-foreground">
                        — {toolTypes[key].category}
                      </span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Name field */}
          {currentType && (
            <>
              <div className="mb-3">
                <label className="mb-1 block text-[11px] text-muted-foreground">Название</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Название инструмента..."
                  className={INPUT_CLASS}
                />
                <p className="text-[10px] text-muted-foreground/50 mt-0.5 font-mono">
                  id: {slugify(name)}
                </p>
              </div>

              {/* Type-specific fields */}
              <div className="space-y-2 mb-3">
                {currentType.fields.map((field) => (
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

              <Button
                type="submit"
                disabled={!name.trim()}
                size="sm"
                className="w-full rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
              >
                <Plus size={12} className="mr-1.5" /> Добавить
              </Button>
            </>
          )}
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

          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" className="flex-1 rounded-full text-xs" onClick={onCancel}>
              Отмена
            </Button>
            <Button type="submit" disabled={!name.trim()} size="sm" className="flex-1 rounded-full bg-slate-950 text-xs text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white">
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
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [deletingToolId, setDeletingToolId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      setIsLoading(true);
      const results = await Promise.allSettled([
        getConfiguredTools(),
        getToolTypes(),
        getPromptTemplates(),
      ]);

      if (!mounted) return;

      if (results[0].status === "fulfilled") setTools(results[0].value);
      if (results[1].status === "fulfilled") setToolTypes(results[1].value);
      if (results[2].status === "fulfilled") setTemplates(results[2].value);
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

  const templateKeys = Object.keys(templates);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200/70 bg-white/80 px-8 py-6 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/45">
        <div className="mx-auto max-w-5xl">
          <div className="overflow-hidden rounded-[30px] border border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.95),rgba(241,245,249,0.92))] px-6 py-6 shadow-[0_28px_80px_-52px_rgba(15,23,42,0.55)] dark:border-slate-800/80 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(2,6,23,0.88))]">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div className="max-w-2xl">
                <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300">
                  Tool Registry
                </span>
                <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">
                  Настройки рабочего пространства
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
                  Здесь живут инструменты, prompt templates и конфигурация для локального multi-agent cockpit.
                  Держи registry в порядке, чтобы сценарии запускались без ручной переклейки.
                </p>
              </div>
              <div className="grid min-w-[220px] grid-cols-2 gap-3">
                <div className="rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Tools</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{tools.length}</p>
                </div>
                <div className="rounded-2xl border border-slate-200/80 bg-white/90 px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
                  <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Templates</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{templateKeys.length}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-5xl space-y-8">
          {/* Section 1: Tools */}
          <section className="rounded-[28px] border border-slate-200/80 bg-white/86 p-6 shadow-[0_24px_70px_-52px_rgba(15,23,42,0.55)] dark:border-slate-800/80 dark:bg-slate-950/50">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings2 size={16} className="text-sky-600 dark:text-sky-300" />
                <h3 className="text-sm font-medium text-slate-950 dark:text-white">Инструменты</h3>
                {tools.length > 0 && (
                  <Badge variant="outline" className="border-slate-200/80 bg-white/85 px-1.5 py-0 text-[10px] font-normal dark:border-slate-800 dark:bg-slate-900/70">
                    {tools.length}
                  </Badge>
                )}
              </div>
              {!showAddForm && (
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full border-slate-200/80 bg-white/85 text-xs dark:border-slate-800 dark:bg-slate-900/70"
                  onClick={() => { setShowAddForm(true); setEditingToolId(null); }}
                >
                  <Plus size={12} className="mr-1" /> Добавить инструмент
                </Button>
              )}
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

                  return (
                    <div
                      key={tool.id}
                      className={cn(
                        "group flex items-center gap-3 rounded-[22px] border border-slate-200/80 bg-white/80 p-3.5 shadow-sm transition-all dark:border-slate-800/80 dark:bg-slate-950/35",
                        !tool.enabled && "opacity-50"
                      )}
                    >
                      {/* Icon */}
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-slate-200/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(241,245,249,0.92))] text-muted-foreground dark:border-slate-800 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.94),rgba(30,41,59,0.72))]">
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
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <Badge variant="outline" className="border-slate-200/80 bg-white/85 px-1.5 py-0 text-[10px] font-normal dark:border-slate-800 dark:bg-slate-900/70">
                            {typeInfo?.category ?? tool.tool_type}
                          </Badge>
                          <span className="text-[10px] text-muted-foreground/50 font-mono">
                            {tool.id}
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
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
                {showAddForm && (
                  <ToolAddForm
                    toolTypes={toolTypes}
                    onAdd={handleAddTool}
                    onCancel={() => setShowAddForm(false)}
                  />
                )}
              </div>
            )}
          </section>

          {/* Section 2: Prompt templates */}
          <section className="rounded-[28px] border border-slate-200/80 bg-white/86 p-6 shadow-[0_24px_70px_-52px_rgba(15,23,42,0.55)] dark:border-slate-800/80 dark:bg-slate-950/50">
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
            <div className="rounded-xl border border-border p-5">
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

            <div className="rounded-xl border border-border p-5 mt-2">
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
