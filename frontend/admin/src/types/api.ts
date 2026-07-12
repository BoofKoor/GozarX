// Response/request shapes for the GozarX admin API (`/api/admin/*`, Phase 7a).

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Me {
  username: string;
}

export interface SetupStatus {
  completed: boolean;
}

export interface Squad {
  uuid: string;
  name: string;
}

export interface EconomicsSettings {
  trial_squad: string | null;
  locations: string[];
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  configs_per_page: number;
  ads_enabled: boolean;
}

export type SettingsPatch = Partial<Omit<EconomicsSettings, "trial_squad">>;

export interface SetupPayload {
  trial_squad: string;
  locations: string[];
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  ads_enabled: boolean;
}

export interface DayPoint {
  day: string;
  count: number;
}

export interface NamedCount {
  label: string;
  count: number;
}

export interface Referrer {
  telegram_id: number;
  referral_count: number;
}

export interface DashboardStats {
  // headline + DB status
  total_users: number;
  available: number;
  active: number;
  banned: number;
  configs_today: number;
  referrals: number;
  range_days: number;
  // user growth
  new_today: number;
  new_this_week: number;
  growth_pct: number;
  // engagement (panel /system/stats)
  online_now: number;
  online_last_day: number;
  online_last_week: number;
  never_online: number;
  panel_online: boolean;
  // trial health & traffic (panel)
  panel_status_counts: Record<string, number>;
  panel_total_users: number;
  total_traffic_bytes: number;
  nodes_online: number;
  // referral & conversion
  conversion_pct: number;
  reminder_enabled: number;
  avg_referrals: number;
  // series + breakdowns
  claims_series: DayPoint[];
  signups_series: DayPoint[];
  languages: NamedCount[];
  top_locations: NamedCount[];
  top_referrers: Referrer[];
}

// --- Phase 7c: texts + buttons editors ---
export type Lang = "fa" | "en" | "ru";
export type LabelMap = Record<Lang, string>;

export interface BotText {
  key: string;
  fa: string;
  en: string;
  ru: string;
  placeholders: string[];
  link_preview: boolean;
}

export type TextPatch = Partial<Record<Lang, string>> & { link_preview?: boolean };

// Telegram Bot API 9.4 inline-button colors (null = the client's default style).
export type ButtonStyle = "primary" | "success" | "danger" | null;

export interface TextPreview {
  rendered: string;
  missing_placeholders: string[];
}

export interface ButtonConfig {
  key: string;
  screen: string;
  is_critical: boolean;
  is_visible: boolean;
  default_row: number;
  default_position: number;
  effective_row: number;
  effective_position: number;
  default_label: LabelMap;
  effective_label: LabelMap;
  style: ButtonStyle;
  customized: boolean;
}

export interface ButtonAppearancePatch {
  labels: Partial<LabelMap> | null;
  is_visible: boolean;
  style?: ButtonStyle;
}

export interface ReorderItem {
  key: string;
  row_index: number;
  position: number;
}

// --- Phase 7d: users + broadcast ---
export interface BotUser {
  telegram_id: number;
  status: string;
  language: string;
  referral_count: number;
  panel_username: string | null;
  reminder_enabled: boolean;
  referred_by: number | null;
  created_at: string | null;
  configs: number | null;
}

export interface UserPage {
  items: BotUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserListParams {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
}

export type UserAction = "ban" | "unban" | "reclaim" | "zero_referrals";

export interface BroadcastAudience {
  recipients: number;
}

export interface BroadcastSend {
  text: string;
  languages: Lang[]; // empty ⇒ everyone; a subset targets only those language groups
}

export interface BroadcastResult {
  queued: boolean;
  recipients: number;
}

// --- system monitoring (/api/admin/system/*) ---
export interface Probe {
  ok: boolean;
  latency_ms: number | null;
  detail: string | null;
}

export interface HostResources {
  load1: number;
  load5: number;
  load15: number;
  cpu_count: number;
  mem_total: number;
  mem_used: number;
  mem_pct: number;
  disk_total: number;
  disk_used: number;
  disk_pct: number;
}

export interface WebhookHealth {
  configured: boolean;
  url_set: boolean;
  pending: number;
  recent_error: boolean;
  last_error_at: string | null;
  last_error: string | null;
}

// Subset of the panel SystemStats surfaced on the monitoring page (extra fields are ignored).
export interface PanelStats {
  cpu_cores: number;
  mem_total: number;
  mem_used: number;
  uptime_seconds: number;
}

export type HealthStatus = "ok" | "degraded" | "down";

export interface SystemHealth {
  status: HealthStatus;
  generated_at: string;
  db: Probe;
  redis: Probe;
  panel: Probe;
  telegram: Probe;
  webhook: WebhookHealth;
  host: HostResources;
  panel_stats: PanelStats | null;
}

export interface HealthSample {
  ts: string;
  status: string;
  api_ms: number | null;
  pending: number;
  db_ms: number | null;
  redis_ms: number | null;
  load1: number;
  mem_pct: number;
  disk_pct: number;
}

// --- Phase 9: website ("site") admin section (/api/admin/site/*) ---
export interface SiteSettings {
  trial_squad: string | null;
  locations: string[];
  popular_location: string | null;
  trial_hours: number;
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  reward_pwa_mb: number;
  reward_push_mb: number;
  reward_streak_mb: number;
  streak_days: number;
}

export type SiteSettingsPatch = Partial<Omit<SiteSettings, "trial_squad">>;

export interface SiteSetupPayload {
  trial_squad: string;
  locations: string[];
  trial_hours: number;
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  reward_pwa_mb: number;
  reward_push_mb: number;
  reward_streak_mb: number;
  streak_days: number;
}

export interface SiteLandingPage {
  id: number;
  slug: string;
  locale: string;
  title: string;
  meta_description: string;
  heading: string | null;
  body: string;
  location_remark: string | null;
  published: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface SiteLandingInput {
  slug: string;
  locale: string;
  title: string;
  meta_description: string;
  heading: string | null;
  body: string;
  location_remark: string | null;
  published: boolean;
}

export interface SiteMessage {
  id: number;
  subject: string;
  body: string;
  reply_handle: string | null;
  locale: string;
  device_uuid: string | null;
  read: boolean;
  created_at: string | null;
}

export interface SiteMessagePage {
  items: SiteMessage[];
  total: number;
  unread: number;
  page: number;
  page_size: number;
}

export interface SitePushAudience {
  recipients: number;
}

export interface SitePushInput {
  title: string;
  body: string;
  url: string;
}

export interface SitePushResult {
  queued: boolean;
  recipients: number;
}

export interface SiteStats {
  total_devices: number;
  devices_claimed: number;
  active_configs: number;
  conversion_pct: number;
  configs_today: number;
  push_subscribers: number;
  range_days: number;
  status_counts: Record<string, number>;
  claims_series: DayPoint[];
  top_locations: NamedCount[];
}
