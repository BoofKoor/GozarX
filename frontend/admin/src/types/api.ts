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
  /** Where this user's LATEST claim came from — null until they have claimed once. */
  last_location: string | null;
  /** When that claim was provisioned — the row's recency signal. Null until they have claimed. */
  last_claim_at: string | null;
}

/** The record dialog's payload: the row, plus this user's history and live usage. */
export interface BotUserDetail extends BotUser {
  claims_series: DayPoint[];
  recent_claims: { location: string; created_at: string }[];
  /** Read live from the panel. NULL when there is no panel account or the panel did not answer —
   *  never a zero standing in for "unknown". */
  traffic_bytes: number | null;
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
  location?: string;
}

export type UserAction = "ban" | "unban" | "reclaim" | "zero_referrals";

export interface BroadcastAudience {
  recipients: number;
}

export interface BroadcastButton {
  text: string;
  /** Telegram rejects a non-https inline URL and fails the WHOLE message. */
  url: string;
}

export interface BroadcastSend {
  text: string;
  languages: Lang[]; // empty ⇒ everyone; a subset targets only those language groups
  only_active?: boolean;
  only_referrers?: boolean;
  buttons?: BroadcastButton[];
  /** ISO instant. Absent ⇒ send now. */
  scheduled_for?: string;
}

/** A broadcast saved before it was sent. `id` present ⇒ overwrite that draft. */
export interface BroadcastDraftSave {
  id?: number;
  text: string;
  languages: Lang[];
  only_active?: boolean;
  only_referrers?: boolean;
  buttons?: BroadcastButton[];
  /** The hour of day that was chosen, not an instant — a saved instant is stale by tomorrow. */
  send_hour?: number | null;
}

export interface BroadcastDraft {
  id: number;
  /** First line of the body, so a draft never had to be named to be kept. */
  title: string;
  body: string;
  /** Comma-separated codes; "" ⇒ everyone. */
  languages: string;
  only_active: boolean;
  only_referrers: boolean;
  buttons: BroadcastButton[];
  send_hour: number | null;
  updated_at: string;
}

/** One past broadcast and how it went. */
export interface BroadcastLog {
  id: number;
  body: string;
  languages: string;
  only_active: boolean;
  only_referrers: boolean;
  buttons: BroadcastButton[];
  status: "queued" | "scheduled" | "sending" | "done" | "failed";
  recipients: number;
  sent: number;
  failed: number;
  /** Its own figure, not folded into `failed`: a user is dropped ONLY on blocked/deactivated. */
  removed: number;
  scheduled_for: string | null;
  created_at: string;
  finished_at: string | null;
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

/** A windowed figure with the same figure over the previous, equal-length window.
 *
 * `change_pct` is `null` (not 0) when there's no baseline — a launch week reads as "new", not
 * "flat", and the two render differently. */
export interface Metric {
  value: number;
  previous: number;
  change_pct: number | null;
}

/** Same shape, but the figure can be genuinely ABSENT rather than zero — a median over an empty
 *  cohort has no value, and rendering it as 0 would claim an instant activation that never
 *  happened. Kept separate from `Metric` because a count always exists and its callers should not
 *  have to narrow a null that can never arrive. */
export interface NullableMetric {
  value: number | null;
  previous: number | null;
  change_pct: number | null;
}

export interface SiteStats {
  range_days: number;

  // Windowed — these move with the range control.
  visitors: Metric; // devices seen in the window
  new_visitors: Metric; // identities minted in the window
  returning_visitors: Metric; // seen in the window, minted before it
  claimers: Metric; // distinct devices that provisioned in the window
  claims: Metric; // provisions in the window (change-location re-picks excluded)
  conversion_pct: number; // claimers / visitors, both windowed
  conversion_pct_prev: number;
  location_changes: number;

  // Lifetime — deliberately OUTSIDE the range control, and named so the UI can say so.
  total_devices_all_time: number;
  devices_claimed_all_time: number;
  conversion_all_time_pct: number;

  // Right now.
  active_configs_live: number; // trial window hasn't elapsed
  active_configs_stale: number; // status still active_config, trial already over (reconcile lag)
  push_subscribers: number;
  configs_today: number; // local Asia/Tehran day
  status_counts: Record<string, number>;

  claims_series: DayPoint[];
  visitors_series: DayPoint[];
  top_locations: NamedCount[];
  locations_total: number; // distinct locations in the window (top_locations is capped at 10)
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
  /** Users who signed up at or after the first referral was recorded — everyone who COULD have
   *  arrived via an invite. The whole user base is the wrong denominator: `referred_by` is null for
   *  every legacy-imported row. */
  eligible: number;
  /** `joined / eligible`. Computed server-side so the panel cannot pick a different denominator. */
  joined_share_pct: number;
}

/** One local day of carried traffic and the concurrency during it. */
export interface UsageDay {
  day: string;
  bytes: number;
  peak_online: number;
  avg_online: number;
  /** The lifetime counter dropped across this day's boundary — a panel restart, a node removed and
   *  re-added, or a traffic reset. `bytes` reads 0 because the true figure is unknowable; this is
   *  what lets the chart say so rather than draw a silent dip. */
  counter_reset: boolean;
}

/** The usage tab's payload. Every figure is windowed, so the range control moves all of them. */
export interface DashboardUsage {
  range_days: number;
  /** When sampling began — null before the first sample. "No traffic in this window" and "we were
   *  not recording yet" are different facts and the empty state has to tell them apart. */
  recording_since: string | null;
  samples: number;
  traffic: Metric;
  peak_online: Metric;
  bytes_per_user: Metric;
  nodes_online: number;
  mem_used: number;
  mem_total: number;
  daily: UsageDay[];
}

export interface DashboardAnalytics {
  range_days: number;
  dau: number;
  wau: number;
  mau: number;
  stickiness_pct: number;
  /** Windowed: the cohort is everyone whose FIRST claim landed in the selected range, next to the
   *  equally long window before it. Both used to be all-time figures under a range control that
   *  could not move them. */
  median_hours_to_claim: NullableMetric;
  activation_24h: Metric;
  first_claimers_in_range: number; // the cohort size both percentages are computed over
  claimers_all_time: number;
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
  /** dau/wau/mau count devices that PROVISIONED; visitors_* count devices that were SEEN. */
  dau: number;
  wau: number;
  mau: number;
  stickiness_pct: number;
  visitors_24h: number;
  visitors_7d: number;
  visitors_30d: number;
  visit_stickiness_pct: number;
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

// --- website FAQ (/api/admin/site/faq/*) ---
/** Category ids the public site builds its tabs from — an item outside this set is rejected. */
export const FAQ_CATEGORIES = ["start", "vol", "apps", "trouble"] as const;
export type FaqCategory = (typeof FAQ_CATEGORIES)[number];

export interface SiteFaqItem {
  id: number;
  locale: string; // fa | en
  category: string;
  question: string;
  answer: string;
  position: number;
  published: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface SiteFaqInput {
  locale: string;
  category: string;
  question: string;
  answer: string;
  published: boolean;
  /** Omitted on create → the item is appended to the end of its locale's list. */
  position?: number | null;
}
