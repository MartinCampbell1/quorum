"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type AppLocale = "ru" | "en";

const dictionaries = {
  ru: {
    shell: {
      appTitle: "AGENT ORCHESTRATOR",
      searchPlaceholder: "Поиск",
      localhostStatus: "Localhost: подключён",
      sessions: "Сессии",
      history: "История",
      settings: "Настройки",
      hideSidebar: "Скрыть список сессий",
      showSidebar: "Показать список сессий",
      account: "Аккаунт",
      theme: "Тема",
      exit: "Выход",
      issues: "2 проблемы",
      loading: "Загрузка...",
      noSessions: "Пока нет сессий",
      noSessionSelected: "Выберите сессию или создайте новую.",
      newSession: "Новая сессия",
      branch: "ветка",
      time: {
        justNow: "только что",
        minutes: "мин",
        hours: "ч",
        days: "д",
      },
    },
    monitor: {
      headerTitle: "Монитор сессии",
      mode: "режим",
      scenario: "сценарий",
      branchOf: "ветка от",
      loading: "Загрузка сессии…",
      activeConnections: "Активные MCP-подключения",
      noActiveConnections: "Пока нет активных MCP-подключений.",
      stopSession: "Остановить сессию",
      resumeSession: "Продолжить сессию",
      restartBranch: "Перезапустить ветку",
      newSession: "Новая сессия",
      exportResults: "Экспортировать",
      checkpointsBranches: "Чекпоинты и ветки",
      parentSession: "Родительская сессия",
      fromCheckpoint: "из чекпоинта",
      childBranches: "Дочерние ветки",
      current: "текущий",
      fork: "Ветвить",
      noCheckpoints: "Чекпоинты появятся после первых переходов графа.",
      selectedHistoricCheckpoint: "Выбран исторический чекпоинт",
      selectedHistoricHint: "Resume всегда идёт с текущего чекпоинта, branch — с выбранного.",
      executionTrace: "Журнал выполнения",
      traceEmpty: "Трасса появится после запуска сессии.",
      toolCall: "Вызов инструмента",
      toolResult: "Результат инструмента",
      failed: "ошибка",
      topologyTitles: {
        board: "Канва совета",
        democracy: "Камера голосования",
        debate: "Арена дебатов",
        creator_critic: "Цикл редакций",
        map_reduce: "Планировщик / исполнители / синтез",
        default: "Топология агентов и MCP",
      },
      sessionTask: "Задача сессии",
      signalLabels: {
        activeNode: "Активный узел",
        checkpoint: "Чекпоинт",
        liveTool: "Живой инструмент",
      },
      noToolActivity: "Пока нет активности по инструментам",
      idle: "ожидание",
      pending: "ожидание",
      genericConnection: "MCP-подключение",
      taskInput: "Входная задача",
      consensusState: "Состояние консенсуса",
      majorityState: "Состояние большинства",
      judgeVerdict: "Вердикт судьи",
      workers: "Исполнители",
      recentChunks: "Последние чанки",
      waitingBoardPosition: "Ожидаем позицию участника совета…",
      waitingVote: "Ожидаем голос…",
      noMajorityYet: "Пока нет большинства. Может понадобиться дополнительный раунд.",
      awaitingArgument: "Ожидаем аргумент…",
      awaitingRebuttal: "Ожидаем возражение…",
      noVerdictYet: "Судья ещё не вынес решение.",
      iterationsHint: "Итерации появятся после обмена версиями между автором и критиком.",
      plannerPreparing: "Планировщик готовит чанки…",
      waitingChunkOutput: "Ожидаем результат по чанку…",
      synthesisPending: "Синтез ещё не завершён…",
    },
    history: {
      title: "История сессий",
      empty: "Пока нет сессий",
      single: "сессия",
      few: "сессии",
      many: "сессий",
    },
    input: {
      checkpointControl: "Управление чекпоинтом",
      sessionPaused: "Сессия остановлена на чекпоинте.",
      sessionPausedHint: "Добавь инструкцию, если хочешь скорректировать следующий шаг, или просто продолжи выполнение.",
      queuedInstructions: "Инструкций в очереди",
      instructionPlaceholder: "Например: проверь гипотезу глубже и опирайся на последние новости по BTC",
      saveInstruction: "Сохранить инструкцию",
      resumeWithInstruction: "Продолжить с инструкцией",
      resume: "Продолжить",
      newBranch: "Новая ветка",
    },
    statuses: {
      running: "работает",
      pause_requested: "ставим на паузу",
      paused: "на паузе",
      cancel_requested: "останавливаем",
      cancelled: "остановлено",
      completed: "готово",
      failed: "ошибка",
    },
  },
  en: {
    shell: {
      appTitle: "AGENT ORCHESTRATOR",
      searchPlaceholder: "Search",
      localhostStatus: "Localhost: connected",
      sessions: "Sessions",
      history: "History",
      settings: "Settings",
      hideSidebar: "Hide session list",
      showSidebar: "Show session list",
      account: "Account",
      theme: "Theme",
      exit: "Exit",
      issues: "2 issues",
      loading: "Loading...",
      noSessions: "No sessions yet",
      noSessionSelected: "Choose a session or create a new one.",
      newSession: "New session",
      branch: "branch",
      time: {
        justNow: "just now",
        minutes: "min",
        hours: "hr",
        days: "d",
      },
    },
    monitor: {
      headerTitle: "Session Monitor",
      mode: "mode",
      scenario: "scenario",
      branchOf: "branch of",
      loading: "Loading session…",
      activeConnections: "Active MCP Connections",
      noActiveConnections: "No active MCP connections yet.",
      stopSession: "Stop Session",
      resumeSession: "Resume Session",
      restartBranch: "Restart Branch",
      newSession: "New Session",
      exportResults: "Export Results",
      checkpointsBranches: "Checkpoints & Branches",
      parentSession: "Parent session",
      fromCheckpoint: "from checkpoint",
      childBranches: "Child branches",
      current: "current",
      fork: "Fork",
      noCheckpoints: "Checkpoints will appear after the first graph transitions.",
      selectedHistoricCheckpoint: "Historical checkpoint selected",
      selectedHistoricHint: "Resume always uses the current checkpoint, branch uses the selected checkpoint.",
      executionTrace: "Execution Trace",
      traceEmpty: "Trace will appear after the session starts.",
      toolCall: "Tool Call",
      toolResult: "Tool Result",
      failed: "failed",
      topologyTitles: {
        board: "Board Consensus Canvas",
        democracy: "Voting Chamber",
        debate: "Debate Arena",
        creator_critic: "Iteration Stack",
        map_reduce: "Planner / Workers / Synthesis",
        default: "Agent & MCP Server Topology",
      },
      sessionTask: "Session Task",
      signalLabels: {
        activeNode: "Active Node",
        checkpoint: "Checkpoint",
        liveTool: "Live Tool",
      },
      noToolActivity: "No tool activity yet",
      idle: "idle",
      pending: "pending",
      genericConnection: "MCP connection",
      taskInput: "Task Input",
      consensusState: "Consensus state",
      majorityState: "Majority state",
      judgeVerdict: "Judge verdict",
      workers: "Workers",
      recentChunks: "Recent chunks",
      waitingBoardPosition: "Waiting for board position…",
      waitingVote: "Waiting for vote…",
      noMajorityYet: "No majority yet. Additional rounds may be required.",
      awaitingArgument: "Awaiting argument…",
      awaitingRebuttal: "Awaiting rebuttal…",
      noVerdictYet: "Judge has not ruled yet.",
      iterationsHint: "Iterations will appear once creator and critic exchange drafts.",
      plannerPreparing: "Planner preparing chunks…",
      waitingChunkOutput: "Waiting for chunk output…",
      synthesisPending: "Synthesis pending…",
    },
    history: {
      title: "Session History",
      empty: "No sessions yet",
      single: "session",
      few: "sessions",
      many: "sessions",
    },
    input: {
      checkpointControl: "Checkpoint Control",
      sessionPaused: "The session is paused on a checkpoint.",
      sessionPausedHint: "Add an instruction if you want to adjust the next step, or simply continue execution.",
      queuedInstructions: "Queued instructions",
      instructionPlaceholder: "For example: inspect the hypothesis deeper and use the latest BTC news",
      saveInstruction: "Save Instruction",
      resumeWithInstruction: "Resume with Instruction",
      resume: "Resume",
      newBranch: "New Branch",
    },
    statuses: {
      running: "running",
      pause_requested: "pausing",
      paused: "paused",
      cancel_requested: "stopping",
      cancelled: "stopped",
      completed: "done",
      failed: "failed",
    },
  },
} as const;

type Dictionary = (typeof dictionaries)[AppLocale];

interface LocaleContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  copy: Dictionary;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<AppLocale>("ru");

  useEffect(() => {
    const stored = window.localStorage.getItem("multi-agent-locale");
    if (stored === "ru" || stored === "en") {
      setLocale(stored);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("multi-agent-locale", locale);
  }, [locale]);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      copy: dictionaries[locale],
    }),
    [locale]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const value = useContext(LocaleContext);
  if (!value) {
    throw new Error("useLocale must be used within LocaleProvider");
  }
  return value;
}
