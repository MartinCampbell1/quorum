"use client";

import { Loader2, LogIn, RefreshCw, ShieldCheck, ShieldX, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AccountHealth, AccountsByProvider, ProviderAccount } from "@/lib/types";

const PROVIDERS = ["codex", "claude", "gemini"] as const;

const PROVIDER_META: Record<(typeof PROVIDERS)[number], { eyebrow: string; accent: string }> = {
  codex: { eyebrow: "OPENAI", accent: "from-sky-500/10 via-cyan-500/8 to-transparent" },
  claude: { eyebrow: "ANTHROPIC", accent: "from-amber-500/10 via-orange-500/8 to-transparent" },
  gemini: { eyebrow: "GOOGLE", accent: "from-violet-500/10 via-fuchsia-500/8 to-transparent" },
};

const INPUT_CLASS =
  "h-9 w-full rounded-[12px] border border-[#d9dde7] bg-white px-3 text-[12px] text-[#111111] outline-none placeholder:text-[#111111]/38 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100";

function formatTime(ts?: number | null) {
  if (!ts) return null;
  const date = new Date(ts * 1000);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  }).format(date);
}

function statusTone(account: ProviderAccount) {
  if (account.available && account.auth_state !== "verified") return "amber";
  if (account.available && account.last_error) return "amber";
  if (account.available) return "emerald";
  if (account.last_error) return "amber";
  return "slate";
}

function statusLabel(account: ProviderAccount) {
  if (account.auth_state === "error" && account.last_error) return "Auth error";
  if (account.available && account.auth_state !== "verified") return "Available (unverified)";
  if (account.available && account.last_error) return "Available with warning";
  if (account.available) return "Available";
  if (account.cooldown_remaining_sec > 0) return `Cooldown ${account.cooldown_remaining_sec}s`;
  if (account.auth_state === "verified") return "Unavailable";
  return "Not checked";
}

export function SettingsAccountsPanel({
  accounts,
  health,
  message,
  busyKey,
  labelDrafts,
  onLabelDraftChange,
  onRefresh,
  onOpenLogin,
  onImport,
  onReauthorize,
  onSaveLabel,
}: {
  accounts: AccountsByProvider;
  health: AccountHealth | null;
  message: string;
  busyKey: string;
  labelDrafts: Record<string, string>;
  onLabelDraftChange: (provider: string, accountName: string, label: string) => void;
  onRefresh: () => void;
  onOpenLogin: (provider: string) => void;
  onImport: (provider: string) => void;
  onReauthorize: (provider: string, accountName: string) => void;
  onSaveLabel: (provider: string, accountName: string) => void;
}) {
  return (
    <section className="rounded-[28px] border border-[#d9dde7] bg-[linear-gradient(180deg,#ffffff_0%,#f9fbff_100%)] p-6 shadow-[0_24px_60px_-46px_rgba(15,23,42,0.24)] dark:border-slate-800 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.9)_0%,rgba(2,6,23,0.86)_100%)]">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#7b8190] dark:text-slate-400">
            Accounts & Reauth
          </p>
          <h2 className="mt-3 text-[2rem] font-semibold tracking-[-0.05em] text-[#09090b] dark:text-slate-50">
            Логин и переавторизация провайдеров
          </h2>
          <p className="mt-3 max-w-2xl text-[14px] leading-7 text-[#5b6476] dark:text-slate-300/80">
            Открой login flow прямо отсюда, заверши auth в Terminal, потом импортируй новую сессию или
            переавторизуй конкретный аккаунт. Для удобства можно подписать аккаунт email или заметкой,
            чтобы быстро понимать, какой профиль сломан.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onRefresh}
            className="h-10 rounded-[12px] border-[#d9dde7] bg-white px-4 text-[13px] dark:border-slate-800 dark:bg-slate-950/50"
          >
            <RefreshCw size={14} className="mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <div className="rounded-[18px] border border-[#e2e8f0] bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-950/55">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7b8190] dark:text-slate-400">
            Imported
          </div>
          <div className="mt-2 text-[24px] font-semibold tracking-[-0.04em] text-[#09090b] dark:text-slate-50">
            {health?.total ?? 0}
          </div>
        </div>
        <div className="rounded-[18px] border border-[#e2e8f0] bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-950/55">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7b8190] dark:text-slate-400">
            Available Now
          </div>
          <div className="mt-2 text-[24px] font-semibold tracking-[-0.04em] text-[#09090b] dark:text-slate-50">
            {health?.available ?? 0}
          </div>
        </div>
        <div className="rounded-[18px] border border-[#e2e8f0] bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-950/55">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#7b8190] dark:text-slate-400">
            Cooling Down
          </div>
          <div className="mt-2 text-[24px] font-semibold tracking-[-0.04em] text-[#09090b] dark:text-slate-50">
            {health?.on_cooldown ?? 0}
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-[18px] border border-[#e2e8f0] bg-white px-4 py-4 text-[13px] leading-6 text-[#5b6476] dark:border-slate-800 dark:bg-slate-950/55 dark:text-slate-300/80">
        <span className="font-medium text-[#111111] dark:text-slate-100">Flow:</span> `Open Login` открывает auth в Terminal.
        После этого жми `Import Current Session`, чтобы добавить новый аккаунт. `Reauthorize` открывает Terminal
        сразу в контексте конкретного `acc*`, чтобы перелогинить именно его, а потом обновить статус через `Refresh`.
        <div className="mt-2 min-h-[20px] text-[12px] text-[#7b8190] dark:text-slate-400">{message || " "}</div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        {PROVIDERS.map((provider) => {
          const providerAccounts = accounts[provider] ?? [];
          const meta = PROVIDER_META[provider];
          const providerBusy = busyKey === `${provider}:login` || busyKey === `${provider}:import`;

          return (
            <section
              key={provider}
              className={cn(
                "overflow-hidden rounded-[24px] border border-[#d9dde7] bg-white shadow-[0_18px_44px_-34px_rgba(15,23,42,0.18)] dark:border-slate-800 dark:bg-slate-950/55"
              )}
            >
              <div className={cn("border-b border-[#edf1f6] bg-gradient-to-br px-5 py-5 dark:border-slate-800", meta.accent)}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7b8190] dark:text-slate-400">
                      {meta.eyebrow}
                    </p>
                    <h3 className="mt-2 text-[18px] font-semibold capitalize tracking-[-0.03em] text-[#09090b] dark:text-slate-50">
                      {provider}
                    </h3>
                  </div>
                  <Badge variant="outline" className="rounded-full border-[#d9dde7] bg-white px-2.5 py-1 text-[11px] dark:border-slate-700 dark:bg-slate-950/60">
                    {providerAccounts.length} acc
                  </Badge>
                </div>
              </div>

              <div className="space-y-3 px-5 py-5">
                {providerAccounts.length === 0 ? (
                  <div className="rounded-[18px] border border-dashed border-[#d9dde7] px-4 py-4 text-[13px] text-[#7b8190] dark:border-slate-800 dark:text-slate-400">
                    Пока нет импортированных аккаунтов.
                  </div>
                ) : (
                  providerAccounts.map((account) => {
                    const tone = statusTone(account);
                    const labelKey = `${provider}:${account.name}`;
                    const busy = busyKey === `${provider}:${account.name}:reauth` || busyKey === `${provider}:${account.name}:label`;
                    const primaryName = account.label?.trim() || account.name;
                    const identityLine =
                      account.identity && account.identity !== primaryName ? account.identity : "";
                    return (
                      <div
                        key={account.name}
                        className="rounded-[18px] border border-[#e6ebf2] bg-[#fbfcff] p-4 dark:border-slate-800 dark:bg-slate-950/40"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <div
                                className="truncate text-[14px] font-medium text-[#09090b] dark:text-slate-100"
                                title={primaryName}
                              >
                                {primaryName}
                              </div>
                              <Badge variant="outline" className="rounded-full border-[#d9dde7] bg-white px-2 py-0 text-[10px] font-medium dark:border-slate-700 dark:bg-slate-950/60">
                                {account.name}
                              </Badge>
                            </div>
                            {identityLine ? (
                              <div
                                className="mt-1 truncate text-[11px] text-[#7b8190] dark:text-slate-400"
                                title={identityLine}
                              >
                                {identityLine}
                              </div>
                            ) : null}
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium",
                                  tone === "emerald" && "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
                                  tone === "amber" && "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
                                  tone === "slate" && "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                                )}
                              >
                                {account.available ? <ShieldCheck size={12} /> : <ShieldX size={12} />}
                                {statusLabel(account)}
                              </span>
                              <span className="text-[11px] text-[#7b8190] dark:text-slate-400">
                                requests: {account.requests_made}
                              </span>
                              {formatTime(account.last_used_at) ? (
                                <span className="text-[11px] text-[#7b8190] dark:text-slate-400">
                                  last used {formatTime(account.last_used_at)}
                                </span>
                              ) : null}
                              {formatTime(account.last_checked_at) ? (
                                <span className="text-[11px] text-[#7b8190] dark:text-slate-400">
                                  checked {formatTime(account.last_checked_at)}
                                </span>
                              ) : null}
                            </div>
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() => onReauthorize(provider, account.name)}
                            className="h-9 rounded-[11px] border-[#d9dde7] bg-white px-3 text-[12px] dark:border-slate-700 dark:bg-slate-950/60"
                          >
                            {busyKey === `${provider}:${account.name}:reauth` ? (
                              <Loader2 size={12} className="mr-1.5 animate-spin" />
                            ) : (
                              <Sparkles size={12} className="mr-1.5" />
                            )}
                            Reauthorize
                          </Button>
                        </div>

                        {account.last_error ? (
                          <div className="mt-3 rounded-[14px] border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
                            {account.last_error}
                          </div>
                        ) : null}

                        <div className="mt-3 flex gap-2">
                          <input
                            value={labelDrafts[labelKey] ?? account.label ?? ""}
                            onChange={(e) => onLabelDraftChange(provider, account.name, e.target.value)}
                            placeholder="email / note / who owns this account"
                            className={INPUT_CLASS}
                          />
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() => onSaveLabel(provider, account.name)}
                            className="h-9 shrink-0 rounded-[11px] border-[#d9dde7] bg-white px-3 text-[12px] dark:border-slate-700 dark:bg-slate-950/60"
                          >
                            {busyKey === `${provider}:${account.name}:label` ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (
                              "Save"
                            )}
                          </Button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div className="grid grid-cols-1 gap-2 border-t border-[#edf1f6] px-5 py-4 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  disabled={providerBusy}
                  onClick={() => onOpenLogin(provider)}
                  className="min-h-10 h-auto w-full rounded-[12px] border-[#d9dde7] bg-white px-3 py-2 text-[12px] leading-tight whitespace-normal dark:border-slate-700 dark:bg-slate-950/60"
                >
                  {busyKey === `${provider}:login` ? (
                    <Loader2 size={13} className="mr-2 animate-spin" />
                  ) : (
                    <LogIn size={13} className="mr-2" />
                  )}
                  Open Login
                </Button>
                <Button
                  type="button"
                  disabled={providerBusy}
                  onClick={() => onImport(provider)}
                  className="min-h-10 h-auto w-full rounded-[12px] bg-[#09090b] px-3 py-2 text-[12px] leading-tight whitespace-normal text-white hover:bg-[#111827] dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                >
                  {busyKey === `${provider}:import` ? (
                    <Loader2 size={13} className="mr-2 animate-spin" />
                  ) : null}
                  Import Current Session
                </Button>
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
}
