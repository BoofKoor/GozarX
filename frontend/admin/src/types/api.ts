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
  total_users: number;
  available: number;
  active: number;
  banned: number;
  configs_today: number;
  referrals: number;
  online_now: number;
  range_days: number;
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

export interface BroadcastResult {
  queued: boolean;
  recipients: number;
}
