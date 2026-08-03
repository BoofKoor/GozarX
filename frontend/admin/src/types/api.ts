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
  // Persian-only promo button on the delivered-config screen (beside "change location").
  ad_button_enabled: boolean;
  ad_button_text: string;
  ad_button_url: string;
  ad_button_emoji_id: string;
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
  growth_pct: number | null; // null = no prior-week baseline (launch); render as "new" when signups > 0
  // Window-over-window comparison: the same figures for the selected range and the equally long
  // window immediately before it. `*_delta_pct` is null when the prior window had no baseline.
  signups_in_range: number;
  signups_prev_range: number;
  signups_delta_pct: number | null;
  claims_in_range: number;
  claims_prev_range: number;
  claims_delta_pct: number | null;
  claimers_in_range: number;
  claimers_prev_range: number;
  claimers_delta_pct: number | null;
  // engagement (panel /system/stats)
  online_now: number;
  online_squad_scoped: boolean;
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
  /** Rows matching the ACTIVE filter — what the pager divides by (`total` counts everything). */
  matching: number;
  unread: number;
  page: number;
  page_size: number;
}

export interface SitePushAudience {
  recipients: number;
  by_locale: { locale: string; count: number }[];
}

export interface SitePushInput {
  title: string;
  body: string;
  url: string;
  /** null (or absent) = every active subscription. */
  locale?: string | null;
}

export interface SitePushResult {
  queued: boolean;
  recipients: number;
  log_id: number;
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

// --- Phase B: dashboard analytics (/api/admin/dashboard/analytics) ---
export interface HeatCell {
  dow: number; // 0=Sunday .. 6=Saturday (Asia/Tehran local)
  hour: number;
  count: number;
}

export interface LangReminder {
  label: string;
  on: number;
  off: number;
}

export interface ReferralFunnel {
  joined: number;
  joined_claimed: number;
  invitee_conversion_pct: number;
  k_factor: number; // avg successful invites per user (viral coefficient)
}

export interface DashboardAnalytics {
  range_days: number;
  dau: number;
  wau: number;
  mau: number;
  stickiness_pct: number;
  median_hours_to_claim: number | null;
  activation_24h_pct: number;
  claimers: number;
  referral: ReferralFunnel;
  referral_cap: ReferralCap;
  heatmap: HeatCell[];
  signup_heatmap: HeatCell[];
  claims_distribution: Record<string, number>; // "1" | "2-3" | "4-6" | "7+" -> users
  reminder_by_language: LangReminder[];
  active_users_series: DayPoint[]; // distinct claimers per day (DAU as a trend, not a point)
  new_vs_returning: SplitDayPoint[];
}

/** One day of the new-vs-returning split: `new` = users whose FIRST-EVER claim was that day. */
export interface SplitDayPoint {
  day: string;
  new: number;
  returning: number;
}

export interface ReferralCap {
  limit: number; // configured reward cap (0 = uncapped)
  at_cap: number; // inviters who hit it and stopped earning
  with_referrals: number;
}

/** A weekly signup cohort. `retention[i]` is the % of the cohort that claimed in the i-th week
 *  after signup; index 0 is the signup week itself (the activation rate). */
export interface CohortRow {
  week: string;
  size: number;
  retention: number[];
}

export interface Retention {
  weeks: number;
  cohorts: CohortRow[];
}

// --- Phase B: site analytics (/api/admin/site/stats/analytics) ---
export interface RewardType {
  type: string;
  grants: number;
  total_mb: number;
}

export interface PushHealth {
  active: number;
  inactive: number;
  by_locale: NamedCount[];
}

export interface AbuseSignals {
  top_ip_buckets: NamedCount[];
  shared_fingerprint_devices: number;
}

export interface SiteAnalytics {
  range_days: number;
  claims_in_range: number;
  devices_active_in_range: number;
  dau: number;
  wau: number;
  mau: number;
  stickiness_pct: number;
  reward_economy: RewardType[];
  streak_distribution: Record<string, number>;
  active_streaks: number;
  push: PushHealth;
  abuse: AbuseSignals;
}

// --- Phase 4: website device browser (/api/admin/site/devices/*) ---
export interface SiteDeviceRow {
  uuid: string;
  handle: string | null;
  status: string; // available | active_config | blocked
  site_panel_username: string | null;
  referral_count: number;
  referred_by: string | null;
  streak_count: number;
  last_claim_at: string | null;
  ip_bucket: string | null;
  has_fingerprint: boolean; // the hash itself is never exposed — it identifies the browser
  created_at: string | null;
}

export interface SiteDevicePage {
  items: SiteDeviceRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface SiteDeviceClaim {
  location: string;
  is_change: boolean;
  created_at: string | null;
}

export interface SiteDeviceCard extends SiteDeviceRow {
  claims: number;
  recent_claims: SiteDeviceClaim[];
  rewards: string[];
  invited: number; // raw, uncapped count of devices that arrived via this one's link
}

export interface SiteDevicePeer {
  uuid: string;
  handle: string | null;
  status: string;
  created_at: string | null;
}

export type SiteDeviceAction = "block" | "unblock" | "reset";

export interface SiteDeviceListParams {
  page: number;
  page_size: number;
  status?: string;
  search?: string;
  ip_bucket?: string;
}

// --- Phase 4: push targeting + history ---
export interface SitePushLog {
  id: number;
  title: string;
  body: string;
  url: string;
  locale: string | null;
  status: string; // queued | sending | done | failed
  recipients: number;
  sent: number;
  failed: number;
  pruned: number;
  created_at: string | null;
  finished_at: string | null;
}

// --- Phase 5: website copy editor (/api/admin/site/content) ---
export interface SiteCopyItem {
  key: string;
  group: string; // seo | hero | widget | sections | push
  fa: string;
  en: string;
  /** What the site renders when the row is blank — its in-code / seeded copy. */
  default_fa: string;
  default_en: string;
  overridden: boolean;
}

export interface SiteCopyPatch {
  fa?: string;
  en?: string;
}
