const TOKEN_KEY = "cadence_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function request<T = unknown>(
  input: RequestInfo,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(input, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      // body wasn't JSON
    }
    if (res.status === 401) {
      setToken(null);
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export interface Habit {
  id: number;
  name: string;
  is_archived: boolean;
}

export type ContinuityContextKind = "project" | "learning" | "area";

export interface ContinuityContext {
  id: number;
  name: string;
  kind: ContinuityContextKind;
  is_archived: boolean;
}

export interface MonthData {
  days: number[];
  month: string;
  habits: Habit[];
  lookup: Record<string, boolean>;
}

export interface DayDetail {
  id: number;
  date: string;
  status: string;
  daily_note: string;
}

export interface Checkin {
  sleep_hours?: number | null;
  sleep_quality?: number | null;
  energy_level?: number | null;
  focus_quality?: number | null;
  emotional_state?: string | null;
  recovery_quality?: number | null;
  reentry_success?: number | null;
  drift_minutes?: number | null;
  notes?: string | null;
}

export interface ConversationEntry {
  id: number;
  role: string;
  content: string;
  created_at: string;
}

export interface RecentDay {
  id: number;
  date: string;
  status: string;
  note_preview: string;
  energy_level: number | null;
  focus_quality: number | null;
}

export interface AIModelRecord {
  id: number;
  provider: string;
  model_id: string;
  strength_score: number;
  ranking_version: string;
  enabled: boolean;
  health_status: string;
  latency_ms: number | null;
  last_error: string | null;
  last_seen_at: string;
  last_tested_at: string | null;
}

export interface AIModelRegistry {
  configured: boolean;
  refreshed: boolean;
  ranking_version: string;
  sync_error?: string;
  models: AIModelRecord[];
}

export interface DailySummary {
  id: number;
  kind: string;
  content: string;
  provider: string | null;
  model: string | null;
  prompt_version: string;
  source_fingerprint: string;
  is_stale: boolean;
  is_user_edited: boolean;
  generated_at: string | null;
  updated_at: string;
}

export interface CarryForwardItem {
  id: number;
  origin_date: string;
  content: string;
  status: "open" | "completed" | "released";
  created_at: string;
  resolved_at: string | null;
}

export interface WeeklyContinuityDay {
  date: string;
  has_entry: boolean;
  status: string | null;
  note_preview: string;
  summary_preview: string;
  energy_level: number | null;
  focus_quality: number | null;
  habit_completions: number;
  contexts: Array<{
    id: number;
    name: string;
    kind: ContinuityContextKind;
  }>;
}

export interface WeeklyContinuity {
  week_start: string;
  week_end: string;
  totals: {
    active_days: number;
    closed_days: number;
    habit_completions: number;
  };
  days: WeeklyContinuityDay[];
  open_threads: Array<{
    id: number;
    origin_date: string;
    content: string;
  }>;
}

export interface WeeklyReflection {
  id: number;
  week_start: string;
  week_end: string;
  content: string;
  provider: string | null;
  model: string | null;
  prompt_version: string;
  source_fingerprint: string;
  is_stale: boolean;
  is_user_edited: boolean;
  generated_at: string | null;
  updated_at: string;
}

export interface WeeklyReflectionHistoryItem {
  id: number;
  week_start: string;
  week_end: string;
  excerpt: string;
  is_user_edited: boolean;
  model: string | null;
  updated_at: string;
}

export interface MonthlyContinuity {
  month: string;
  month_start: string;
  month_end: string;
  totals: {
    active_days: number;
    closed_days: number;
    habit_completions: number;
    weekly_reflections: number;
  };
  days: Array<{
    date: string;
    status: string;
    trace_preview: string;
    trace_source: "summary" | "note" | null;
    energy_level: number | null;
    focus_quality: number | null;
    checkin_fields: number;
    habit_completions: number;
    conversation_entries: number;
    contexts: Array<{
      id: number;
      name: string;
      kind: ContinuityContextKind;
    }>;
  }>;
  weekly_reflections: Array<{
    id: number;
    week_start: string;
    week_end: string;
    excerpt: string;
    is_user_edited: boolean;
    model: string | null;
  }>;
  contexts: Array<{
    id: number;
    name: string;
    kind: ContinuityContextKind;
    active_days: number;
    last_date: string;
    last_trace_preview: string;
  }>;
  open_threads: Array<{
    id: number;
    origin_date: string;
    content: string;
  }>;
}

export interface DisciplineMonthlyContinuity {
  discipline: Habit;
  month: string;
  month_start: string;
  month_end: string;
  totals: {
    completed_days: number;
    linked_trace_days: number;
    contexts: number;
  };
  previous_completion: { date: string; excerpt: string } | null;
  days: Array<{
    date: string;
    status: string;
    trace_preview: string;
    trace_source: "summary" | "note" | null;
    conversation_entries: number;
    contexts: Array<{
      id: number;
      name: string;
      kind: ContinuityContextKind;
    }>;
  }>;
  contexts: Array<{
    id: number;
    name: string;
    kind: ContinuityContextKind;
    completed_days: number;
  }>;
}

export interface CadenceDataExport {
  format: "cadence-export";
  schema_version: number;
  exported_at: string;
  account: {
    username: string;
    email: string;
    is_verified: boolean;
  };
  resources: Record<string, unknown[]>;
}

export interface AIPreferences {
  processing_consent: boolean;
  redaction_enabled: boolean;
  provider: string;
  external_processing: boolean;
  redaction_scope: string;
}

export interface ContinuityPatterns {
  start_date: string;
  end_date: string;
  weeks: number;
  totals: {
    recorded_days: number;
    active_weeks: number;
  };
  weekly: Array<{
    week_start: string;
    week_end: string;
    active_days: number;
    habit_completions: number;
    average_energy: number | null;
    average_focus: number | null;
  }>;
  observations: Array<{
    kind: "rhythm" | "context" | "return";
    title: string;
    body: string;
    evidence: Record<string, string | number>;
  }>;
  interpretation: string;
}

export interface ContextMonthlyContinuity {
  context: ContinuityContext;
  month: string;
  month_start: string;
  month_end: string;
  totals: {
    active_days: number;
    closed_days: number;
    habit_completions: number;
    conversation_entries: number;
  };
  previous_activity: {
    date: string;
    excerpt: string;
    source: "summary" | "note" | null;
  } | null;
  weeks: Array<{
    week_start: string;
    week_end: string;
    active_days: number;
    closed_days: number;
    habit_completions: number;
    last_date: string;
    last_trace_preview: string;
  }>;
  days: Array<{
    date: string;
    status: string;
    trace_preview: string;
    trace_source: "summary" | "note" | null;
    energy_level: number | null;
    focus_quality: number | null;
    habit_completions: number;
    conversation_entries: number;
  }>;
  open_threads: Array<{
    id: number;
    origin_date: string;
    content: string;
  }>;
}

export type ContinuitySearchSource =
  | "all"
  | "notes"
  | "conversation"
  | "summaries"
  | "threads"
  | "weekly_reflections";

export interface ContinuitySearchResult {
  source: Exclude<ContinuitySearchSource, "all">;
  source_id: number;
  date: string;
  title: string;
  excerpt: string;
  status?: string;
}

export interface ContinuitySearchResponse {
  query: string;
  source: ContinuitySearchSource;
  context_id: number | null;
  start_date: string;
  end_date: string;
  results: ContinuitySearchResult[];
}

export interface ContextContinuity {
  context: ContinuityContext;
  recent_days: Array<{
    date: string;
    status: string;
    note_preview: string;
    summary_preview: string;
    energy_level: number | null;
    focus_quality: number | null;
    habit_completions: number;
  }>;
  open_threads: Array<{
    id: number;
    origin_date: string;
    content: string;
  }>;
}

export interface DailyReentry {
  date: string;
  previous_trace: {
    date: string;
    source: "summary" | "note";
    excerpt: string;
  } | null;
  open_threads: Array<{
    id: number;
    origin_date: string;
    content: string;
  }>;
  contexts: Array<{
    id: number;
    name: string;
    kind: ContinuityContextKind;
    last_activity: {
      date: string;
      source: "summary" | "note" | null;
      excerpt: string;
    } | null;
  }>;
}

export interface DayClosurePreview {
  date: string;
  status: "open" | "closed";
  capture: {
    has_daily_note: boolean;
    conversation_entries: number;
    completed_habits: number;
    checkin_fields: number;
  };
  summary: {
    exists: boolean;
    excerpt: string;
    is_user_edited: boolean;
  };
  open_thread_count: number;
  open_threads: Array<{
    id: number;
    origin_date: string;
    content: string;
  }>;
}

export async function fetchHabits(): Promise<Habit[]> {
  return request<Habit[]>("/api/habits");
}

export function fetchContexts(
  includeArchived = false,
): Promise<ContinuityContext[]> {
  return request<ContinuityContext[]>(
    `/api/contexts${includeArchived ? "?include_archived=true" : ""}`,
  );
}

export function createContext(
  name: string,
  kind: ContinuityContextKind,
): Promise<ContinuityContext> {
  return request<ContinuityContext>("/api/contexts", {
    method: "POST",
    body: JSON.stringify({ name, kind }),
  });
}

export function updateContext(
  contextId: number,
  name: string,
  kind: ContinuityContextKind,
): Promise<ContinuityContext> {
  return request<ContinuityContext>(`/api/contexts/${contextId}`, {
    method: "PATCH",
    body: JSON.stringify({ name, kind }),
  });
}

export function archiveContext(
  contextId: number,
): Promise<ContinuityContext> {
  return request<ContinuityContext>(`/api/contexts/${contextId}`, {
    method: "DELETE",
  });
}

export function fetchDayContexts(
  date: string,
): Promise<ContinuityContext[]> {
  return request<ContinuityContext[]>(`/api/days/${date}/contexts`);
}

export function updateDayContexts(
  date: string,
  contextIds: number[],
): Promise<ContinuityContext[]> {
  return request<ContinuityContext[]>(`/api/days/${date}/contexts`, {
    method: "PUT",
    body: JSON.stringify({ context_ids: contextIds }),
  });
}

export function fetchContextContinuity(
  contextId: number,
  limit = 12,
): Promise<ContextContinuity> {
  return request<ContextContinuity>(
    `/api/contexts/${contextId}/continuity?limit=${limit}`,
  );
}

export function fetchContextMonthlyContinuity(
  contextId: number,
  month: string,
): Promise<ContextMonthlyContinuity> {
  return request<ContextMonthlyContinuity>(
    `/api/contexts/${contextId}/months/${month}`,
  );
}

export function createHabit(name: string): Promise<Habit> {
  return request<Habit>("/api/habits", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function renameHabit(habitId: number, name: string): Promise<Habit> {
  return request<Habit>(`/api/habits/${habitId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function archiveHabit(habitId: number): Promise<Habit> {
  return request<Habit>(`/api/habits/${habitId}`, {
    method: "DELETE",
  });
}

export async function fetchMonthData(month: string): Promise<MonthData> {
  return request<MonthData>(`/api/habits/month?month=${month}`);
}

export async function toggleHabit(
  habitId: number,
  date: string,
  value: string,
): Promise<void> {
  await request("/api/habits/toggle", {
    method: "POST",
    body: JSON.stringify({ habit_id: habitId, date, value }),
  });
}

export function fetchDay(date: string): Promise<DayDetail> {
  return request<DayDetail>(`/api/days/${date}`);
}

export function fetchDayReentry(date: string): Promise<DailyReentry> {
  return request<DailyReentry>(`/api/days/${date}/reentry`);
}

export function fetchClosurePreview(
  date: string,
): Promise<DayClosurePreview> {
  return request<DayClosurePreview>(`/api/days/${date}/closure`);
}

export function fetchRecentDays(limit = 7): Promise<RecentDay[]> {
  return request<RecentDay[]>(`/api/days?limit=${limit}`);
}

export function updateDay(date: string, dailyNote: string): Promise<DayDetail> {
  return request<DayDetail>(`/api/days/${date}`, {
    method: "PUT",
    body: JSON.stringify({ daily_note: dailyNote }),
  });
}

export function updateDayStatus(
  date: string,
  status: "open" | "closed",
): Promise<DayDetail> {
  return request<DayDetail>(`/api/days/${date}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function fetchCheckin(date: string): Promise<Checkin> {
  return request<Checkin>(`/api/days/${date}/checkin`);
}

export function updateCheckin(date: string, checkin: Checkin): Promise<Checkin> {
  return request<Checkin>(`/api/days/${date}/checkin`, {
    method: "PUT",
    body: JSON.stringify(checkin),
  });
}

export function fetchConversation(date: string): Promise<ConversationEntry[]> {
  return request<ConversationEntry[]>(`/api/days/${date}/conversation`);
}

export function addConversationEntry(
  date: string,
  content: string,
): Promise<ConversationEntry> {
  return request<ConversationEntry>(`/api/days/${date}/conversation`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function fetchSummary(date: string): Promise<DailySummary | null> {
  return request<DailySummary | null>(`/api/days/${date}/summary`);
}

export function updateSummary(
  date: string,
  content: string,
): Promise<DailySummary> {
  return request<DailySummary>(`/api/days/${date}/summary`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export function generateSummary(
  date: string,
  replaceEdited = false,
): Promise<DailySummary> {
  return request<DailySummary>(`/api/days/${date}/summary/generate`, {
    method: "POST",
    body: JSON.stringify({ replace_edited: replaceEdited }),
  });
}

export function fetchCarryForward(date: string): Promise<CarryForwardItem[]> {
  return request<CarryForwardItem[]>(`/api/days/${date}/carry-forward`);
}

export function createCarryForward(
  date: string,
  content: string,
): Promise<CarryForwardItem> {
  return request<CarryForwardItem>(`/api/days/${date}/carry-forward`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function updateCarryForwardStatus(
  date: string,
  itemId: number,
  status: CarryForwardItem["status"],
): Promise<CarryForwardItem> {
  return request<CarryForwardItem>(
    `/api/days/${date}/carry-forward/${itemId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
}

export function fetchWeeklyContinuity(
  anchorDate: string,
): Promise<WeeklyContinuity> {
  return request<WeeklyContinuity>(
    `/api/continuity/weeks/${anchorDate}`,
  );
}

export function fetchMonthlyContinuity(
  month: string,
): Promise<MonthlyContinuity> {
  return request<MonthlyContinuity>(
    `/api/continuity/months/${month}`,
  );
}

export function fetchDisciplineMonthlyContinuity(
  disciplineId: number,
  month: string,
): Promise<DisciplineMonthlyContinuity> {
  return request<DisciplineMonthlyContinuity>(
    `/api/habits/${disciplineId}/months/${month}`,
  );
}

export function fetchDataExport(): Promise<CadenceDataExport> {
  return request<CadenceDataExport>("/api/account/export");
}

export function fetchAIPreferences(): Promise<AIPreferences> {
  return request<AIPreferences>("/api/account/ai-preferences");
}

export function updateAIPreferences(
  processingConsent: boolean,
  redactionEnabled: boolean,
): Promise<AIPreferences> {
  return request<AIPreferences>("/api/account/ai-preferences", {
    method: "PUT",
    body: JSON.stringify({
      processing_consent: processingConsent,
      redaction_enabled: redactionEnabled,
    }),
  });
}

export function fetchContinuityPatterns(
  anchorDate: string,
  weeks = 8,
): Promise<ContinuityPatterns> {
  const params = new URLSearchParams({
    anchor_date: anchorDate,
    weeks: String(weeks),
  });
  return request<ContinuityPatterns>(
    `/api/continuity/patterns?${params.toString()}`,
  );
}

export function fetchWeeklyReflection(
  anchorDate: string,
): Promise<WeeklyReflection | null> {
  return request<WeeklyReflection | null>(
    `/api/continuity/weeks/${anchorDate}/reflection`,
  );
}

export function updateWeeklyReflection(
  anchorDate: string,
  content: string,
): Promise<WeeklyReflection> {
  return request<WeeklyReflection>(
    `/api/continuity/weeks/${anchorDate}/reflection`,
    {
      method: "PUT",
      body: JSON.stringify({ content }),
    },
  );
}

export function generateWeeklyReflection(
  anchorDate: string,
  replaceEdited = false,
): Promise<WeeklyReflection> {
  return request<WeeklyReflection>(
    `/api/continuity/weeks/${anchorDate}/reflection/generate`,
    {
      method: "POST",
      body: JSON.stringify({ replace_edited: replaceEdited }),
    },
  );
}

export function fetchWeeklyReflectionHistory(
  limit = 8,
): Promise<WeeklyReflectionHistoryItem[]> {
  return request<WeeklyReflectionHistoryItem[]>(
    `/api/continuity/reflections?limit=${limit}`,
  );
}

export function searchContinuity(
  query: string,
  source: ContinuitySearchSource = "all",
  contextId?: number,
): Promise<ContinuitySearchResponse> {
  const params = new URLSearchParams({ q: query, source });
  if (contextId != null) {
    params.set("context_id", String(contextId));
  }
  return request<ContinuitySearchResponse>(
    `/api/continuity/search?${params.toString()}`,
  );
}

export function fetchAIModels(refresh = false): Promise<AIModelRegistry> {
  return request<AIModelRegistry>(
    `/api/dev/ai/models${refresh ? "?refresh=true" : ""}`,
  );
}

export function testAIModels(
  modelIds: string[] = [],
  testAll = false,
): Promise<{
  tested: number;
  models: AIModelRecord[];
}> {
  return request("/api/dev/ai/models/test", {
    method: "POST",
    body: JSON.stringify({ model_ids: modelIds, test_all: testAll }),
  });
}
